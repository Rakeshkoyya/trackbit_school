"""Homework analytics (HW-1) — completion, and whether anyone is checking.

Two questions this answers that the old count could not:

  1. **Which students keep not doing it**, with the subject and the teacher
     responsible — because `homework_results` now names them.
  2. **Which teachers set homework and never look at it.** A missing
     `homework_checks` row means "not checked", which is a fact about the
     teacher, not the class. Folding it into completion would let a teacher who
     checks nothing show a perfect record, so `not_checked` is counted and
     reported separately and NEVER as a student miss.

Everything is a computed join over capture (P5); nothing here is stored.

Query budget: five statements for the whole overview regardless of school size —
assignments, checks, results, rosters, names — joined in memory. A per-class or
per-student loop would be one remote round-trip each, which is the failure mode
this codebase keeps having to design around.
"""

import uuid
from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core import homework_verdict as verdicts
from app.core.context import CurrentMember
from app.core.exceptions import ForbiddenError, NotFoundError
from app.models import (
    AcademicYear,
    ClassSubject,
    HomeworkAssignment,
    HomeworkCheck,
    HomeworkResult,
    Membership,
    PeriodSubstitution,
    SchoolClass,
    Student,
    Subject,
    User,
)
from app.schemas.homework import (
    HomeworkDay,
    HomeworkFunnel,
    HomeworkLoad,
    HomeworkLoadCell,
    HomeworkMatrixCell,
    HomeworkOverview,
    HomeworkQueue,
    HomeworkQueueItem,
    HomeworkScopeRow,
    RoughClassRow,
    StudentHomeworkHistory,
    StudentHomeworkItem,
    StudentHomeworkRow,
    TeacherCheckingRow,
)
from app.services.attendance import day_absence_maps, is_day_absent
from app.services.school_clock import today_in

WINDOW_DAYS = 14
# A student is on the red list at this many consecutive homework days missed.
STREAK_ALERT = 2
MAX_LIST = 25
# D-85's second signal fires at this many misses on ONE checked homework. A
# constant, not a setting (DASH3 10.4): the school has no basis to tune it yet,
# and a threshold nobody understands is worse than one nobody can change.
MASS_MISS_ALERT = 5


def _label(name: str, section: str | None) -> str:
    return name + (f"-{section}" if section else "")


def _pct(done: int, total: int) -> float | None:
    return round(done / total, 3) if total else None


def _tone(pct: float | None) -> str:
    """Percent → the board's tone. One place, so the matrix cell, the row bar
    and the summary block cannot each decide what "low" means."""
    if pct is None:
        return "neutral"
    return "green" if pct >= 0.75 else "amber" if pct >= 0.60 else "red"


def bucket_days(window_days: int) -> int:
    """One column per day for a fortnight, one per week beyond it.

    A year at one column per day is 365 marks nobody can read, and the shape —
    which is the only reason the series exists — survives weekly buckets fine.
    """
    return 1 if window_days <= 21 else 7


def _bucket_label(start: date, days: int) -> str:
    """The bucket's own name. Composed here rather than in the browser because
    a week bucket is not a date and the client has no way to know which it got.
    """
    if days == 1:
        # Built by hand rather than with %-d/%#d, which differ by platform.
        return f"{start.strftime('%a')} {start.day}"
    end = start + timedelta(days=days - 1)
    if start.month == end.month:
        return f"{start.day}–{end.day} {start.strftime('%b')}"
    return f"{start.day} {start.strftime('%b')} – {end.day} {end.strftime('%b')}"


class HomeworkService:
    def __init__(self, db: Session):
        self.db = db

    def _today(self, m: CurrentMember) -> date:
        return today_in(m.org.timezone)

    def _year(self, org_id: uuid.UUID) -> AcademicYear | None:
        return self.db.scalar(
            select(AcademicYear).where(AcademicYear.org_id == org_id,
                                       AcademicYear.is_active.is_(True)))

    # ── the shared load: everything the window needs, in five queries ────────
    def _load(self, m: CurrentMember, since: date, until: date,
              student_id: uuid.UUID | None = None):
        rows = self.db.execute(
            select(HomeworkAssignment, SchoolClass.id, SchoolClass.name, SchoolClass.section,
                   Subject.name, ClassSubject.teacher_member_id)
            .join(ClassSubject, ClassSubject.id == HomeworkAssignment.class_subject_id)
            .join(SchoolClass, SchoolClass.id == ClassSubject.class_id)
            .join(Subject, Subject.id == ClassSubject.subject_id)
            .where(HomeworkAssignment.org_id == m.org_id,
                   HomeworkAssignment.date >= since, HomeworkAssignment.date <= until)
            .order_by(HomeworkAssignment.date)
        ).all()
        if student_id is not None:
            rows = [r for r in rows
                    if r[0].student_id in (None, student_id)]
        assignments = [
            {"hw": hw, "class_id": cid, "class_label": _label(cname, section),
             "subject": sname, "teacher_member_id": tid}
            for hw, cid, cname, section, sname, tid in rows
        ]
        ids = [a["hw"].id for a in assignments]
        if not ids:
            return assignments, {}, defaultdict(dict), {}, {}

        checks = {
            c.assignment_id: c for c in self.db.scalars(
                select(HomeworkCheck).where(HomeworkCheck.assignment_id.in_(ids)))
        }
        results: dict[uuid.UUID, dict[uuid.UUID, HomeworkResult]] = defaultdict(dict)
        for r in self.db.scalars(
                select(HomeworkResult).where(HomeworkResult.assignment_id.in_(ids))):
            results[r.assignment_id][r.student_id] = r

        class_ids = {a["class_id"] for a in assignments}
        roster: dict[uuid.UUID, list[tuple]] = defaultdict(list)
        if class_ids:
            q = select(Student.id, Student.full_name, Student.class_id, Student.roll_no).where(
                Student.org_id == m.org_id, Student.status == "active",
                Student.class_id.in_(class_ids))
            if student_id is not None:
                q = q.where(Student.id == student_id)
            for sid, name, cid, roll in self.db.execute(q).all():
                roster[cid].append((sid, name, roll))

        teacher_ids = {a["teacher_member_id"] for a in assignments if a["teacher_member_id"]}
        teachers = {
            mid: name for mid, name in self.db.execute(
                select(Membership.id, User.name)
                .join(User, User.id == Membership.user_id)
                .where(Membership.id.in_(teacher_ids))).all()
        } if teacher_ids else {}
        return assignments, checks, results, roster, teachers

    @staticmethod
    def _targets(a: dict, roster: dict) -> list[tuple]:
        """Who a homework is for: one student if personal, else the class."""
        hw = a["hw"]
        pool = roster.get(a["class_id"], [])
        if hw.student_id is None:
            return pool
        return [s for s in pool if s[0] == hw.student_id]

    @staticmethod
    def _status(a: dict, student_id: uuid.UUID, checks: dict, results: dict) -> str:
        if a["hw"].id not in checks:
            return "not_checked"
        hit = results.get(a["hw"].id, {}).get(student_id)
        return hit.status if hit else "done"

    # The streak lives in `core/homework_verdict` so the admin board, the
    # teacher's check sheet (S-89) and the report card all show one number.
    _streak = staticmethod(verdicts.miss_streak)

    # ── admin overview ───────────────────────────────────────────────────────
    def overview(self, m: CurrentMember, window_days: int = WINDOW_DAYS) -> HomeworkOverview:
        until = self._today(m)
        since = until - timedelta(days=max(1, window_days) - 1)
        assignments, checks, results, roster, teachers = self._load(m, since, until)

        if not assignments:
            return HomeworkOverview(window_days=window_days, from_date=since, to_date=until,
                                    assigned=0, checked=0, check_rate=None,
                                    overall_completion=None)

        # scope accumulators: key → the verdict tally plus assigned/checked.
        def _acc() -> dict[str, int]:
            # `not_checked` is carried through the accumulators so it can be
            # reported, and `graded` deliberately excludes it — that separation
            # is HW-1's load-bearing rule and this is where it is enforced.
            #
            # `students_set` / `students_checked` are the funnel's first two
            # stages. They live in the same accumulator as the verdicts so every
            # scope — school, class, subject, day, class×subject — gets all
            # three stages from one addition and none of them can drift.
            return {"assigned": 0, "checked": 0, "students_set": 0,
                    "students_checked": 0, "done": 0, "late": 0, "partial": 0,
                    "not_done": 0, "carried": 0, "waived": 0, "not_checked": 0,
                    "graded": 0}

        by_class: dict[str, dict[str, int]] = defaultdict(_acc)
        by_subject: dict[str, dict[str, int]] = defaultdict(_acc)
        # The two cuts the old board could not draw: one bucket per day (the
        # shape) and one per class×subject (where a low number actually lives).
        by_day: dict[date, dict[str, int]] = defaultdict(_acc)
        by_cell: dict[tuple[str, str], dict[str, int]] = defaultdict(_acc)
        # teacher → [assigned, checked, unchecked_overdue, last_checked_at]
        by_teacher: dict[uuid.UUID | None, list] = defaultdict(lambda: [0, 0, 0, None])
        per_student: dict[uuid.UUID, dict] = {}
        totals = _acc()
        # D-85's second admin signal: this class WAS checked, and N children
        # missed it. Different from "nobody checked" and needing a different
        # conversation, so it is counted separately rather than buried in a rate.
        rough: list[tuple[int, dict]] = []

        # S-85/D-34: a child who was day-absent when the homework was set never
        # reads as a miss. The verdict becomes `carried` — pending, not refused —
        # so it leaves every figure, the streak and the red list that fires
        # guardian reminders. Day-absence comes from THE shared rule
        # (services/attendance.py), not a local one.
        marked_by_class, absents_by_student = day_absence_maps(
            self.db, m.org_id, since, until)

        def _absent_when_set(class_id: uuid.UUID, on: date, sid: uuid.UUID) -> bool:
            return is_day_absent(marked_by_class.get((class_id, on), 0),
                                 absents_by_student.get(sid, {}).get(on, 0))

        for a in assignments:
            hw = a["hw"]
            checked = hw.id in checks
            targets = self._targets(a, roster)
            counts = _acc()
            for sid, name, roll in targets:
                status = self._status(a, sid, checks, results)
                # The teacher can say "carried" explicitly; attendance says it
                # for her when she hasn't. Either way it is one verdict.
                if (verdicts.is_miss(status)
                        and _absent_when_set(a["class_id"], hw.date, sid)):
                    status = "carried"
                counts[status] = counts.get(status, 0) + 1
                if verdicts.is_graded(status):
                    counts["graded"] += 1

                rec = per_student.setdefault(sid, {
                    "name": name, "roll": roll, "class_label": a["class_label"],
                    "assigned": 0, "done": 0, "late": 0, "not_done": 0, "partial": 0,
                    "carried": 0, "waived": 0,
                    "dated": [], "subjects": set(), "teachers": set()})
                rec["assigned"] += 1
                rec["dated"].append((hw.date, status))
                if status in rec:
                    rec[status] += 1
                if verdicts.is_miss(status):
                    rec["subjects"].add(a["subject"])
                    if a["teacher_member_id"]:
                        rec["teachers"].add(teachers.get(a["teacher_member_id"], "—"))

            counts["assigned"] = 1
            counts["checked"] = 1 if checked else 0
            # Stage 1 and stage 2 of the funnel, in student-homeworks. An
            # unchecked set contributes its whole roster to `students_set` and
            # nothing to `students_checked` — which is exactly the gap the
            # board exists to show, and exactly what the old three numbers
            # (two of them counted in sets) could not express.
            counts["students_set"] = len(targets)
            counts["students_checked"] = len(targets) if checked else 0
            for bucket, key in ((by_class, a["class_label"]), (by_subject, a["subject"])):
                for k, v in counts.items():
                    bucket[key][k] += v
            for k, v in counts.items():
                by_day[hw.date][k] += v
                by_cell[(a["class_label"], a["subject"])][k] += v
                totals[k] += v

            misses = counts["not_done"] + counts["partial"]
            if checked and misses >= MASS_MISS_ALERT:
                rough.append((misses, {
                    "class_label": a["class_label"], "subject": a["subject"],
                    "date": hw.date, "text": hw.text, "assignment_id": hw.id,
                    "graded": counts["graded"],
                    "teacher": teachers.get(a["teacher_member_id"]) if a["teacher_member_id"] else None,
                }))

            t = by_teacher[a["teacher_member_id"]]
            t[0] += 1
            if checked:
                t[1] += 1
                stamp = checks[hw.id].checked_at
                if stamp and (t[3] is None or stamp > t[3]):
                    t[3] = stamp
            else:
                # Only overdue homework counts against a teacher — homework set an
                # hour ago is not a failure to check.
                deadline = hw.due_date or hw.date
                if deadline < until:
                    t[2] += 1

        def scope_rows(bucket: dict) -> list[HomeworkScopeRow]:
            return sorted(
                (HomeworkScopeRow(
                    key=key, assigned=v["assigned"], checked=v["checked"],
                    students_expected=v["graded"],
                    students_set=v["students_set"],
                    students_checked=v["students_checked"],
                    done=v["done"], not_done=v["not_done"], partial=v["partial"],
                    late=v["late"], carried=v["carried"], waived=v["waived"],
                    # ONE arithmetic (core/homework_verdict): late counts as done,
                    # partly counts PARTIAL_WEIGHT, carried/waived are not in it.
                    completion=verdicts.completion(v), check_rate=_pct(v["checked"], v["assigned"]))
                 for key, v in bucket.items()),
                key=lambda r: (r.completion if r.completion is not None else 2, r.key))

        teacher_rows = sorted(
            (TeacherCheckingRow(
                member_id=mid, teacher_name=teachers.get(mid, "Unassigned") if mid else "Unassigned",
                assigned=v[0], checked=v[1], unchecked_overdue=v[2],
                check_rate=_pct(v[1], v[0]), last_checked_at=v[3])
             for mid, v in by_teacher.items()),
            key=lambda r: (r.check_rate if r.check_rate is not None else 0, -r.unchecked_overdue))

        # ── the funnel: three stages, one unit, both denominators named ──────
        funnel = HomeworkFunnel(
            given=totals["students_set"],
            checked=totals["students_checked"],
            graded=totals["graded"],
            done=totals["done"], late=totals["late"], partial=totals["partial"],
            not_done=totals["not_done"], carried=totals["carried"],
            waived=totals["waived"],
            # The one arithmetic. `completion` divides exactly this, so no
            # screen has to reconstruct the numerator from the parts and get
            # `partial` wrong on the way.
            done_weighted=round(
                totals["done"] + totals["late"]
                + verdicts.verdict_weight("partial") * totals["partial"], 2),
            assignments=totals["assigned"],
            class_subjects=len({(a["class_label"], a["subject"]) for a in assignments}),
            check_rate=_pct(totals["students_checked"], totals["students_set"]),
            completion=verdicts.completion(totals))

        # ── the series, bucketed so a long range stays readable ──────────────
        size = bucket_days(window_days)
        buckets: dict[date, dict[str, int]] = defaultdict(_acc)
        for day, v in by_day.items():
            # Anchored on the window's start so the buckets are stable as the
            # window slides, rather than on the first day that happened to
            # carry homework.
            start = since + timedelta(days=((day - since).days // size) * size)
            for k, n in v.items():
                buckets[start][k] += n
        daily = [
            HomeworkDay(
                date=start, label=_bucket_label(start, size), days=size,
                assigned=v["assigned"], checked=v["checked"],
                given=v["students_set"], expected=v["graded"],
                # `done` here means the child did the work — late included,
                # because late IS done (S-99). Reported beside it, never as a
                # separate slice that makes the column look short.
                done=v["done"] + v["late"],
                partial=v["partial"], not_done=v["not_done"],
                not_checked=v["not_checked"],
                completion=verdicts.completion(v))
            for start, v in sorted(buckets.items())
        ]

        # ── class × subject: where a low number actually lives ───────────────
        matrix = [
            HomeworkMatrixCell(
                class_key=ck, subject_key=sk, assigned=v["assigned"],
                checked=v["checked"], given=v["students_set"],
                graded=v["graded"], completion=verdicts.completion(v),
                tone=_tone(verdicts.completion(v)))
            for (ck, sk), v in by_cell.items()
        ]
        matrix_classes = sorted({c for c, _ in by_cell})
        matrix_subjects = sorted({s for _, s in by_cell})

        students = []
        for sid, rec in per_student.items():
            counts = verdicts.tally(st for _d, st in rec["dated"])
            students.append(StudentHomeworkRow(
                student_id=sid, full_name=rec["name"], class_label=rec["class_label"],
                roll_no=rec["roll"], assigned=rec["assigned"], done=rec["done"],
                not_done=rec["not_done"], partial=rec["partial"],
                late=rec["late"], carried=rec["carried"],
                completion=verdicts.completion(counts),
                streak=self._streak(rec["dated"]),
                subjects=sorted(rec["subjects"]), teachers=sorted(rec["teachers"])))

        needs = sorted(
            [s for s in students
             if s.streak >= STREAK_ALERT or (s.not_done + s.partial) >= 3],
            key=lambda s: (-s.streak, -(s.not_done + s.partial)))[:MAX_LIST]
        perfect = sorted(
            [s for s in students if s.done > 0 and s.not_done == 0 and s.partial == 0],
            key=lambda s: (-s.done, s.full_name))[:MAX_LIST]

        # Most improved: misses in the recent half of the window against the earlier
        # half. A student with nothing in either half cannot have improved.
        midpoint = since + timedelta(days=max(1, window_days) // 2)
        improved: list[StudentHomeworkRow] = []
        for s in students:
            rec = per_student[s.student_id]
            early = sum(1 for d, st in rec["dated"] if d < midpoint and verdicts.is_miss(st))
            recent = sum(1 for d, st in rec["dated"] if d >= midpoint and verdicts.is_miss(st))
            if early > recent:
                s2 = s.model_copy()
                # Its own field. This used to overwrite `streak`, so the row
                # claimed a miss streak it did not have and the screen printed
                # "N fewer misses" from a field named for the opposite thing.
                s2.improvement = early - recent
                improved.append(s2)
        improved.sort(key=lambda s: -s.improvement)

        rough.sort(key=lambda r: -r[0])
        return HomeworkOverview(
            window_days=window_days, from_date=since, to_date=until,
            assigned=totals["assigned"], checked=totals["checked"],
            check_rate=_pct(totals["checked"], totals["assigned"]),
            overall_completion=verdicts.completion(totals),
            late=totals["late"], carried=totals["carried"],
            funnel=funnel, daily=daily, matrix=matrix,
            matrix_classes=matrix_classes, matrix_subjects=matrix_subjects,
            by_class=scope_rows(by_class), by_subject=scope_rows(by_subject),
            teachers=teacher_rows, needs_attention=needs, perfect=perfect,
            most_improved=improved[:10],
            delayed_teachers=self._delayed_teachers(m, teacher_rows, until),
            rough_classes=[
                RoughClassRow(assignment_id=r["assignment_id"], class_label=r["class_label"],
                              subject_name=r["subject"], date=r["date"], text=r["text"],
                              missed=n, students_expected=r["graded"],
                              teacher_name=r["teacher"])
                for n, r in rough[:MAX_LIST]])

    def _delayed_teachers(self, m: CurrentMember, rows: list[TeacherCheckingRow],
                          until: date) -> list[TeacherCheckingRow]:
        """D-85's first admin signal: *this teacher has not checked anything for
        N days.*

        **Derived, never written into a child's record.** That separation is the
        whole of `D-85`: the child being late is a status the teacher sets in her
        own words, and the teacher being late is this — read from `checked_at`,
        reported to the admin, and invisible on every student surface.

        A teacher with nothing overdue is not delayed, however long ago she last
        checked: a quiet fortnight is not a failure to check work nobody set.
        """
        cutoff = until - timedelta(days=max(1, m.org.homework_gap_days))
        out = [
            r for r in rows
            if r.unchecked_overdue > 0
            and (r.last_checked_at is None or r.last_checked_at.date() <= cutoff)
        ]
        return sorted(out, key=lambda r: -r.unchecked_overdue)[:MAX_LIST]

    # ── one student (feeds the growth report and the parent portal) ──────────
    def student_history(self, m: CurrentMember, student_id: uuid.UUID,
                        window_days: int = WINDOW_DAYS) -> StudentHomeworkHistory:
        student = self.db.scalar(
            select(Student).where(Student.id == student_id, Student.org_id == m.org_id))
        if student is None:
            raise NotFoundError("Student")
        # A teacher may only read a student they actually teach.
        if not m.is_admin:
            teaches = self.db.scalar(
                select(ClassSubject.id).where(
                    ClassSubject.org_id == m.org_id,
                    ClassSubject.class_id == student.class_id,
                    ClassSubject.teacher_member_id == m.membership.id).limit(1))
            if teaches is None:
                raise ForbiddenError("That student isn't in a class you teach.",
                                     code="not_your_student")
        return self.history_for(m.org_id, student, window_days, self._today(m))

    def history_for(self, org_id: uuid.UUID, student: Student, window_days: int,
                    until: date) -> StudentHomeworkHistory:
        """Access-free core, so the parent projection can reuse it (that layer
        does its own guardian-link check and never passes a CurrentMember)."""
        since = until - timedelta(days=max(1, window_days) - 1)
        rows = self.db.execute(
            select(HomeworkAssignment, SchoolClass.name, SchoolClass.section, Subject.name)
            .join(ClassSubject, ClassSubject.id == HomeworkAssignment.class_subject_id)
            .join(SchoolClass, SchoolClass.id == ClassSubject.class_id)
            .join(Subject, Subject.id == ClassSubject.subject_id)
            .where(HomeworkAssignment.org_id == org_id,
                   ClassSubject.class_id == student.class_id,
                   HomeworkAssignment.date >= since, HomeworkAssignment.date <= until,
                   or_(HomeworkAssignment.student_id.is_(None),
                       HomeworkAssignment.student_id == student.id))
            .order_by(HomeworkAssignment.date.desc())
        ).all()
        ids = [hw.id for hw, _, _, _ in rows]
        checked = set(self.db.scalars(
            select(HomeworkCheck.assignment_id)
            .where(HomeworkCheck.assignment_id.in_(ids)))) if ids else set()
        mine = {
            r.assignment_id: r for r in self.db.scalars(
                select(HomeworkResult).where(
                    HomeworkResult.assignment_id.in_(ids),
                    HomeworkResult.student_id == student.id))
        } if ids else {}

        items: list[StudentHomeworkItem] = []
        dated: list[tuple[date, str]] = []
        statuses: list[str] = []
        for hw, cname, section, sname in rows:
            if hw.id not in checked:
                status = "not_checked"
            else:
                hit = mine.get(hw.id)
                status = hit.status if hit else "done"
            statuses.append(status)
            dated.append((hw.date, status))
            items.append(StudentHomeworkItem(
                assignment_id=hw.id, date=hw.date, due_date=hw.due_date,
                subject_name=sname, class_label=_label(cname, section), text=hw.text,
                personal=hw.student_id is not None, status=status,
                note=mine[hw.id].note if hw.id in mine else None))

        counts = verdicts.tally(statuses)
        klass = self.db.get(SchoolClass, student.class_id) if student.class_id else None
        return StudentHomeworkHistory(
            student_id=student.id, full_name=student.full_name,
            class_label=_label(klass.name, klass.section) if klass else None,
            window_days=window_days, assigned=len(items), done=counts["done"],
            not_done=counts["not_done"], partial=counts["partial"],
            late=counts["late"], carried=counts["carried"], waived=counts["waived"],
            not_checked=counts["not_checked"],
            # The one arithmetic — this used to divide by a hand-rolled graded
            # count that silently disagreed with the board's (late was missing).
            completion=verdicts.completion(counts),
            streak=self._streak(dated), items=items)

    # ── the teacher's Homework screen (D-36 / S-101) ────────────────────────
    def queue(self, m: CurrentMember, window_days: int = 30,
              class_subject_id: uuid.UUID | None = None,
              on_date: date | None = None) -> HomeworkQueue:
        """Her classes × what was given, **oldest unchecked first**.

        `D-36` moved checking off My Day onto its own screen, because checking is
        a desk activity with a stack of notebooks rather than a between-classes
        tap. `S-100` is what decides whether that works: the button carries the
        count, and the count is this query's `to_check`. An unlabelled button is
        how a daily habit becomes a monthly one.

        Ordering is the point (`S-83`): everything unchecked past its deadline,
        oldest first, so Friday's homework survives the weekend and a day missed
        is a day recovered rather than a record lost. Nothing expires (`D-85`).
        """
        until = on_date or self._today(m)
        since = until - timedelta(days=max(1, window_days) - 1)

        mine = self._my_class_subjects(m)
        if class_subject_id is not None:
            mine = [cs for cs in mine if cs == class_subject_id]
        if not mine:
            return HomeworkQueue(from_date=since, to_date=until, to_check=0)

        rows = self.db.execute(
            select(HomeworkAssignment, SchoolClass.name, SchoolClass.section, Subject.name,
                   Student.full_name)
            .join(ClassSubject, ClassSubject.id == HomeworkAssignment.class_subject_id)
            .join(SchoolClass, SchoolClass.id == ClassSubject.class_id)
            .join(Subject, Subject.id == ClassSubject.subject_id)
            .outerjoin(Student, Student.id == HomeworkAssignment.student_id)
            .where(HomeworkAssignment.org_id == m.org_id,
                   HomeworkAssignment.class_subject_id.in_(mine),
                   HomeworkAssignment.date >= since, HomeworkAssignment.date <= until)
            .order_by(HomeworkAssignment.date.desc())).all()
        ids = [hw.id for hw, *_ in rows]
        checks = {
            c.assignment_id: c for c in self.db.scalars(
                select(HomeworkCheck).where(HomeworkCheck.assignment_id.in_(ids)))
        } if ids else {}
        misses: dict[uuid.UUID, int] = defaultdict(int)
        carried: dict[uuid.UUID, int] = defaultdict(int)
        if ids:
            for aid, status, n in self.db.execute(
                select(HomeworkResult.assignment_id, HomeworkResult.status,
                       func.count(HomeworkResult.id))
                .where(HomeworkResult.assignment_id.in_(ids))
                .group_by(HomeworkResult.assignment_id, HomeworkResult.status)).all():
                if verdicts.is_miss(status):
                    misses[aid] += int(n)
                elif status == "carried":
                    carried[aid] += int(n)

        items: list[HomeworkQueueItem] = []
        for hw, cname, section, sname, student_name in rows:
            check = checks.get(hw.id)
            deadline = hw.due_date or hw.date
            items.append(HomeworkQueueItem(
                assignment_id=hw.id, class_subject_id=hw.class_subject_id,
                class_label=_label(cname, section), subject_name=sname,
                date=hw.date, due_date=hw.due_date, text=hw.text,
                student_id=hw.student_id, student_name=student_name,
                checked=check is not None,
                checked_at=check.checked_at if check else None,
                # Overdue is a fact about the record, not a judgement: it means
                # the deadline has passed with nothing gone through yet.
                overdue=check is None and deadline < until,
                days_waiting=max(0, (until - deadline).days) if check is None else 0,
                missed=misses.get(hw.id, 0), carried=carried.get(hw.id, 0)))

        # Unchecked first and oldest-first inside that, then the checked ones
        # newest-first — the top of the list is always the work still to do.
        items.sort(key=lambda i: (i.checked, i.date if not i.checked else -i.date.toordinal()))
        return HomeworkQueue(
            from_date=since, to_date=until, items=items,
            to_check=sum(1 for i in items if not i.checked),
            overdue=sum(1 for i in items if i.overdue))

    def _my_class_subjects(self, m: CurrentMember) -> list[uuid.UUID]:
        """The class-subjects this member may check — hers, plus any she covered.

        Admins get everything: they are the ones chasing the checking, and a
        board that hid the classes they do not personally teach would be empty.
        """
        if m.is_admin:
            return list(self.db.scalars(
                select(ClassSubject.id).where(ClassSubject.org_id == m.org_id)))
        own = set(self.db.scalars(
            select(ClassSubject.id).where(
                ClassSubject.org_id == m.org_id,
                ClassSubject.teacher_member_id == m.membership.id)))
        # S-93: a substitute can check the homework in front of her, so the
        # classes she covered have to reach her queue in the first place.
        own.update(self.db.scalars(
            select(PeriodSubstitution.class_subject_id).where(
                PeriodSubstitution.org_id == m.org_id,
                PeriodSubstitution.substitute_member_id == m.membership.id,
                PeriodSubstitution.cancelled_at.is_(None),
                PeriodSubstitution.class_subject_id.is_not(None))))
        return list(own)

    # ── D-37 / S-87: what one class was given in one evening ────────────────
    def daily_load(self, m: CurrentMember, class_id: uuid.UUID | None = None,
                   days: int = 14) -> HomeworkLoad:
        """How many subjects set homework for a class, per day.

        Six teachers each set thirty minutes of work, independently, and until
        now no screen anywhere added them up — the child has three hours and the
        school has six reasonable decisions. This needs no new capture at all:
        it is `homework_assignments` grouped by class × date.

        **Admin and class teacher only** (`D-37`). A subject teacher sees none of
        it, deliberately: the number exists to be discussed in the staff room,
        not to make one teacher feel they should have set less.

        Informational — **no cap and no rota** (`D-37`). A limit turns into
        "whose turn is it to set homework", which is worse than the problem.
        """
        until = self._today(m)
        since = until - timedelta(days=max(1, days) - 1)
        allowed = self._load_scope(m, class_id)
        if not allowed:
            return HomeworkLoad(from_date=since, to_date=until)

        rows = self.db.execute(
            select(SchoolClass.id, SchoolClass.name, SchoolClass.section,
                   HomeworkAssignment.date,
                   func.count(func.distinct(ClassSubject.subject_id)),
                   func.count(HomeworkAssignment.id))
            .join(ClassSubject, ClassSubject.id == HomeworkAssignment.class_subject_id)
            .join(SchoolClass, SchoolClass.id == ClassSubject.class_id)
            .where(HomeworkAssignment.org_id == m.org_id,
                   SchoolClass.id.in_(allowed),
                   # Class-wide homework only: a personal note to one child is
                   # not part of what the class was given that evening.
                   HomeworkAssignment.student_id.is_(None),
                   HomeworkAssignment.date >= since, HomeworkAssignment.date <= until)
            .group_by(SchoolClass.id, SchoolClass.name, SchoolClass.section,
                      HomeworkAssignment.date)
            .order_by(HomeworkAssignment.date)).all()

        cells = [
            HomeworkLoadCell(class_id=cid, class_label=_label(cname, section), date=d,
                             subjects=int(nsub), assignments=int(nass))
            for cid, cname, section, d, nsub, nass in rows
        ]
        busiest = max(cells, key=lambda c: c.subjects, default=None)
        return HomeworkLoad(
            from_date=since, to_date=until, cells=cells,
            busiest_class_label=busiest.class_label if busiest else None,
            busiest_date=busiest.date if busiest else None,
            busiest_subjects=busiest.subjects if busiest else 0)

    def _load_scope(self, m: CurrentMember, class_id: uuid.UUID | None) -> list[uuid.UUID]:
        """Which classes' load this member may read (D-37). Admin: all. Class
        teacher: her own class. Anyone else: nothing, and that is the feature."""
        q = select(SchoolClass.id).where(SchoolClass.org_id == m.org_id)
        if not m.is_admin:
            q = q.where(SchoolClass.class_teacher_member_id == m.membership.id)
        if class_id is not None:
            q = q.where(SchoolClass.id == class_id)
        return list(self.db.scalars(q))

    # ── small reads for other services ──────────────────────────────────────
    def unchecked_count(self, m: CurrentMember, on_or_before: date | None = None) -> int:
        """Homework past its deadline that nobody has gone through — the number
        the daily report and the dashboard raise."""
        until = on_or_before or self._today(m)
        return int(self.db.scalar(
            select(func.count(HomeworkAssignment.id))
            .outerjoin(HomeworkCheck, HomeworkCheck.assignment_id == HomeworkAssignment.id)
            .where(HomeworkAssignment.org_id == m.org_id,
                   HomeworkCheck.id.is_(None),
                   func.coalesce(HomeworkAssignment.due_date, HomeworkAssignment.date) < until,
                   HomeworkAssignment.date >= until - timedelta(days=WINDOW_DAYS))) or 0)
