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

from app.core.context import CurrentMember
from app.core.exceptions import ForbiddenError, NotFoundError
from app.models import (
    AcademicYear,
    ClassSubject,
    HomeworkAssignment,
    HomeworkCheck,
    HomeworkResult,
    Membership,
    SchoolClass,
    Student,
    Subject,
    User,
)
from app.schemas.homework import (
    HomeworkOverview,
    HomeworkScopeRow,
    StudentHomeworkHistory,
    StudentHomeworkItem,
    StudentHomeworkRow,
    TeacherCheckingRow,
)
from app.services.school_clock import today_in

WINDOW_DAYS = 14
# A student is on the red list at this many consecutive homework days missed.
STREAK_ALERT = 2
MAX_LIST = 25


def _label(name: str, section: str | None) -> str:
    return name + (f"-{section}" if section else "")


def _pct(done: int, total: int) -> float | None:
    return round(done / total, 3) if total else None


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

    @staticmethod
    def _streak(dated: list[tuple[date, str]]) -> int:
        """Consecutive most-recent homework days that were missed.

        Counts by DAY, not by assignment: three subjects missed on one afternoon
        is one bad day, not a three-day streak. Days with nothing checked are
        skipped rather than breaking the run — the teacher's gap is not the
        student's, and treating it as a clean day would hide a real pattern.
        """
        by_day: dict[date, bool] = {}
        for d, status in dated:
            if status == "not_checked":
                continue
            by_day[d] = by_day.get(d, False) or status in ("not_done", "partial")
        streak = 0
        for d in sorted(by_day, reverse=True):
            if not by_day[d]:
                break
            streak += 1
        return streak

    # ── admin overview ───────────────────────────────────────────────────────
    def overview(self, m: CurrentMember, window_days: int = WINDOW_DAYS) -> HomeworkOverview:
        until = self._today(m)
        since = until - timedelta(days=max(1, window_days) - 1)
        assignments, checks, results, roster, teachers = self._load(m, since, until)

        if not assignments:
            return HomeworkOverview(window_days=window_days, from_date=since, to_date=until,
                                    assigned=0, checked=0, check_rate=None,
                                    overall_completion=None)

        # scope accumulators: key → [assigned, checked, expected, done, not_done, partial]
        by_class: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0, 0, 0, 0])
        by_subject: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0, 0, 0, 0])
        # teacher → [assigned, checked, unchecked_overdue]
        by_teacher: dict[uuid.UUID | None, list] = defaultdict(lambda: [0, 0, 0, None])
        per_student: dict[uuid.UUID, dict] = {}
        totals = [0, 0, 0, 0, 0, 0]

        for a in assignments:
            hw = a["hw"]
            checked = hw.id in checks
            targets = self._targets(a, roster)
            n_done = n_not = n_part = 0
            for sid, name, roll in targets:
                status = self._status(a, sid, checks, results)
                rec = per_student.setdefault(sid, {
                    "name": name, "roll": roll, "class_label": a["class_label"],
                    "assigned": 0, "done": 0, "not_done": 0, "partial": 0,
                    "dated": [], "subjects": set(), "teachers": set()})
                rec["assigned"] += 1
                rec["dated"].append((hw.date, status))
                if status == "done":
                    rec["done"] += 1
                    n_done += 1
                elif status == "not_done":
                    rec["not_done"] += 1
                    n_not += 1
                    rec["subjects"].add(a["subject"])
                    if a["teacher_member_id"]:
                        rec["teachers"].add(teachers.get(a["teacher_member_id"], "—"))
                elif status == "partial":
                    rec["partial"] += 1
                    n_part += 1
                    rec["subjects"].add(a["subject"])

            expected = len(targets) if checked else 0
            for bucket, key in ((by_class, a["class_label"]), (by_subject, a["subject"])):
                acc = bucket[key]
                acc[0] += 1
                acc[1] += 1 if checked else 0
                acc[2] += expected
                acc[3] += n_done
                acc[4] += n_not
                acc[5] += n_part
            totals[0] += 1
            totals[1] += 1 if checked else 0
            totals[2] += expected
            totals[3] += n_done
            totals[4] += n_not
            totals[5] += n_part

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
                    key=key, assigned=v[0], checked=v[1], students_expected=v[2],
                    done=v[3], not_done=v[4], partial=v[5],
                    completion=_pct(v[3], v[2]), check_rate=_pct(v[1], v[0]))
                 for key, v in bucket.items()),
                key=lambda r: (r.completion if r.completion is not None else 2, r.key))

        teacher_rows = sorted(
            (TeacherCheckingRow(
                member_id=mid, teacher_name=teachers.get(mid, "Unassigned") if mid else "Unassigned",
                assigned=v[0], checked=v[1], unchecked_overdue=v[2],
                check_rate=_pct(v[1], v[0]), last_checked_at=v[3])
             for mid, v in by_teacher.items()),
            key=lambda r: (r.check_rate if r.check_rate is not None else 0, -r.unchecked_overdue))

        students = []
        for sid, rec in per_student.items():
            misses = rec["not_done"] + rec["partial"]
            graded = rec["done"] + misses
            students.append(StudentHomeworkRow(
                student_id=sid, full_name=rec["name"], class_label=rec["class_label"],
                roll_no=rec["roll"], assigned=rec["assigned"], done=rec["done"],
                not_done=rec["not_done"], partial=rec["partial"],
                completion=_pct(rec["done"], graded),
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
            early = sum(1 for d, st in rec["dated"] if d < midpoint and st in ("not_done", "partial"))
            late = sum(1 for d, st in rec["dated"] if d >= midpoint and st in ("not_done", "partial"))
            if early > late:
                s2 = s.model_copy()
                s2.streak = early - late  # reuse as the improvement delta for sorting
                improved.append(s2)
        improved.sort(key=lambda s: -s.streak)

        return HomeworkOverview(
            window_days=window_days, from_date=since, to_date=until,
            assigned=totals[0], checked=totals[1], check_rate=_pct(totals[1], totals[0]),
            overall_completion=_pct(totals[3], totals[2]),
            by_class=scope_rows(by_class), by_subject=scope_rows(by_subject),
            teachers=teacher_rows, needs_attention=needs, perfect=perfect,
            most_improved=improved[:10])

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
        tally = {"done": 0, "not_done": 0, "partial": 0, "not_checked": 0}
        dated: list[tuple[date, str]] = []
        for hw, cname, section, sname in rows:
            if hw.id not in checked:
                status = "not_checked"
            else:
                hit = mine.get(hw.id)
                status = hit.status if hit else "done"
            tally[status] += 1
            dated.append((hw.date, status))
            items.append(StudentHomeworkItem(
                assignment_id=hw.id, date=hw.date, due_date=hw.due_date,
                subject_name=sname, class_label=_label(cname, section), text=hw.text,
                personal=hw.student_id is not None, status=status,
                note=mine[hw.id].note if hw.id in mine else None))

        graded = tally["done"] + tally["not_done"] + tally["partial"]
        klass = self.db.get(SchoolClass, student.class_id) if student.class_id else None
        return StudentHomeworkHistory(
            student_id=student.id, full_name=student.full_name,
            class_label=_label(klass.name, klass.section) if klass else None,
            window_days=window_days, assigned=len(items), done=tally["done"],
            not_done=tally["not_done"], partial=tally["partial"],
            not_checked=tally["not_checked"], completion=_pct(tally["done"], graded),
            streak=self._streak(dated), items=items)

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
