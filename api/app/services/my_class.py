"""My Class — the class teacher's area (V1-3 `D-03`; expanded 2026-08-05).

Centred on the month attendance grid: student × school day, each cell THE day
status from `classify_marked_day` (ux §9 — the same classifier the admin board
and the parent strip render). A row's shape says "every Monday" or "a block in
October" or "slowly fading" faster than any percentage.

The 2026-08-05 expansion makes it the class teacher's whole desk rather than one
grid: an overview that answers her six morning questions, the roster as a table
whose rows open a child's file, the class's syllabus across **all** subjects,
homework, the support tiers, and her own log about a child.

**It composes; it computes almost nothing.** Coverage comes from
`MySyllabusService`, homework arithmetic from `core/homework_verdict`, exams from
`ExamService.feed`, bands from `BandService.placements`, attendance from
`day_matrix` and `classify_marked_day`. That is not tidiness — it is what stops a
class teacher and her principal reading different numbers for the same Tuesday,
which is the `S-51` defect this codebase keeps closing. The only arithmetic
written here is the roll-up of facts those services return.

Access: the class teacher of THIS class, or an admin. Another teacher gets 403 —
her children are the point of the assignment.
"""

import uuid
from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.coverage import PARTIAL_WEIGHT
from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.homework_verdict import is_miss, tally, verdict_weight
from app.models import (
    AcademicYear,
    AssessmentCycle,
    AssessmentScore,
    AttendanceException,
    ClassPeriod,
    ClassSubject,
    Guardian,
    HomeworkAssignment,
    HomeworkCheck,
    HomeworkResult,
    Intervention,
    Membership,
    SchoolClass,
    Student,
    StudentAbsenceNote,
    StudentCategory,
    StudentNote,
    Subject,
    TimetableSlot,
    User,
)
from app.schemas.my_class import (
    HomeworkDayRow,
    HomeworkItem,
    HomeworkMissRow,
    MyClassAbsentee,
    MyClassAttendance,
    MyClassBands,
    MyClassBandStudent,
    MyClassBandSubject,
    MyClassExams,
    MyClassHomework,
    MyClassHomeworkDay,
    MyClassHomeworkDays,
    MyClassOut,
    MyClassOverview,
    MyClassStudentRow,
    MyClassStudentsOut,
    MyClassSummary,
    RegisterOut,
    StudentNoteIn,
    StudentNoteOut,
    StudentNotesOut,
)
from app.services.attendance import build_register, classify_marked_day, day_matrix
from app.services.bands import BandService
from app.services.calendar import org_working_days
from app.services.exam_marks import load_class_marks
from app.services.exams import ExamService
from app.services.insights.actions import ActionService
from app.services.my_syllabus import MySyllabusService
from app.services.periods import visible_class_ids
from app.services.school_clock import marking_period_nos, today_in
from app.services.syllabus_board import SyllabusBoardService

# Day statuses that mean "the child was in school at some point".
PRESENT_STATUSES = ("present", "partial", "left_after_lunch")

# The homework funnel's window. Two school weeks: long enough that a class with
# one unchecked evening does not read as a crisis, short enough that it is still
# about this term rather than the year.
HOMEWORK_WINDOW = 14
# The roster table's window — a month, because an attendance percentage over two
# weeks moves too far on one absence to be worth putting beside a name.
STUDENT_WINDOW = 30
EXAM_FEED_LIMIT = 6
MAX_NOTES = 100


def _label(klass: SchoolClass) -> str:
    return klass.name + (f"-{klass.section}" if klass.section else "")


def _plural(n: int, one: str, many: str | None = None) -> str:
    return one if n == 1 else (many or one + "s")


class MyClassService:
    def __init__(self, db: Session):
        self.db = db

    def my_classes(self, m: CurrentMember) -> MyClassOut:
        """The classes this member is class teacher of (admin: all classes)."""
        q = select(SchoolClass).where(SchoolClass.org_id == m.org_id)
        if not m.is_admin:
            q = q.where(SchoolClass.class_teacher_member_id == m.membership.id)
        classes = list(self.db.scalars(q.order_by(SchoolClass.name, SchoolClass.section)))
        rosters = {}
        if classes:
            from sqlalchemy import func  # noqa: PLC0415
            rosters = dict(self.db.execute(
                select(Student.class_id, func.count(Student.id))
                .where(Student.org_id == m.org_id, Student.status == "active",
                       Student.class_id.in_([c.id for c in classes]))
                .group_by(Student.class_id)).all())
        return MyClassOut(classes=[
            MyClassSummary(class_id=c.id, class_label=_label(c),
                           roster=rosters.get(c.id, 0),
                           is_mine=c.class_teacher_member_id == m.membership.id)
            for c in classes])

    def _guard(self, m: CurrentMember, klass: SchoolClass) -> None:
        if m.is_admin:
            return
        if klass.class_teacher_member_id != m.membership.id:
            raise ForbiddenError("This is not your class.", code="not_your_class")

    def _klass(self, m: CurrentMember, class_id: uuid.UUID) -> SchoolClass:
        """Fetch + guard in one call — every method below starts with this, so
        there is no path into the area that forgot to check whose class it is."""
        klass = self.db.scalar(select(SchoolClass).where(
            SchoolClass.id == class_id, SchoolClass.org_id == m.org_id))
        if klass is None:
            raise NotFoundError("Class")
        self._guard(m, klass)
        return klass

    def _class_roster(self, m: CurrentMember, class_id: uuid.UUID) -> list[Student]:
        return list(self.db.scalars(
            select(Student).where(
                Student.org_id == m.org_id, Student.class_id == class_id,
                Student.status == "active").order_by(Student.full_name)))

    def register(self, m: CurrentMember, class_id: uuid.UUID,
                 month: str | None = None) -> RegisterOut:
        """The month grid, for HER class. The drawing is `build_register`; this
        adds only the homeroom guard."""
        return build_register(self.db, m, self._klass(m, class_id), month)

    # ── the overview: her six morning questions, in one payload ──────────────
    def overview(self, m: CurrentMember, class_id: uuid.UUID) -> MyClassOverview:
        klass = self._klass(m, class_id)
        today = today_in(m.org.timezone)
        roster = self._class_roster(m, class_id)

        attendance = self._attendance_block(m, klass, roster, today)
        homework = self._homework_block(m, class_id, today)
        bands = self._bands_block(m, roster, klass=klass)
        exams = self._exams_block(m, class_id)
        syllabus = self._syllabus_block(m, class_id)

        # The sentence leads, and it names the ONE thing actually waiting. A
        # headline reciting five figures would be the stat row this replaced.
        if not attendance.marked and attendance.school_open:
            headline = (f"The register has not been taken yet — {len(roster)} "
                        f"{_plural(len(roster), 'child', 'children')} on the roll.")
        elif attendance.absentees:
            n = len(attendance.absentees)
            unexplained = sum(1 for a in attendance.absentees if not a.explained)
            headline = (f"{n} {_plural(n, 'child is', 'children are')} away today"
                        + (f", {unexplained} with no reason on record."
                           if unexplained else ", every one explained."))
        elif homework.unchecked_assignments:
            n = homework.unchecked_assignments
            headline = (f"Everyone is in. {n} {_plural(n, 'homework')} nobody has "
                        "gone through yet.")
        else:
            headline = "Everyone is in, and nothing is waiting."

        return MyClassOverview(
            class_id=class_id, class_label=_label(klass), roster=len(roster),
            as_of=today, headline=headline, attendance=attendance,
            homework=homework, bands=bands, exams=exams, syllabus=syllabus)

    # ── attendance ───────────────────────────────────────────────────────────
    def _attendance_block(self, m: CurrentMember, klass: SchoolClass,
                          roster: list[Student], today: date) -> MyClassAttendance:
        """Today for this class, plus the month it sits in.

        The 2026-08-05 rule applied here too: **the day is today whenever the
        school is open**, marked or not, and `roster` is the class's strength
        regardless. A class teacher's first question is "has it been taken?",
        and yesterday's figures under today's heading answer a different one.
        """
        open_today = bool(org_working_days(self.db, m.org_id, today, today))
        year = self.db.get(AcademicYear, klass.academic_year_id)
        marking = marking_period_nos(
            year.period_times if year else None, m.org.attendance_mode)

        marked, exc = day_matrix(self.db, m.org_id, [klass.id], today, today)
        periods = marked.get((klass.id, today), [])
        scheduled = self._scheduled_periods(m, klass, today)

        block = MyClassAttendance(
            date=today, is_today=True, school_open=open_today,
            marked=bool(periods), roster=len(roster),
            periods_marked=len(periods), periods_scheduled=scheduled)

        if periods:
            absentees: list[MyClassAbsentee] = []
            late = 0
            for s in roster:
                per = exc.get((s.id, today), {})
                status, was_late = classify_marked_day(
                    periods, {p: st for p, (st, _r) in per.items()}, marking)
                if was_late:
                    late += 1
                if status in ("absent", "partial", "left_after_lunch"):
                    absentees.append(MyClassAbsentee(
                        student_id=s.id, full_name=s.full_name, roll_no=s.roll_no,
                        status=status))
            block.absent = sum(1 for a in absentees if a.status == "absent")
            block.late = late
            block.present = len(roster) - block.absent
            block.pct = round(block.present / len(roster) * 100, 1) if roster else None
            block.absentees = self._decorate_absentees(m, absentees, today)

        # The month, from the same register the tab draws.
        first = today.replace(day=1)
        month_marked, month_exc = day_matrix(self.db, m.org_id, [klass.id], first, today)
        captured = sorted({d for (_c, d) in month_marked if month_marked[(_c, d)]})
        present_days = absent_days = 0
        for d in captured:
            per_day = month_marked.get((klass.id, d), [])
            if not per_day:
                continue
            for s in roster:
                per = month_exc.get((s.id, d), {})
                status, _l = classify_marked_day(
                    per_day, {p: st for p, (st, _r) in per.items()}, marking)
                if status == "absent":
                    absent_days += 1
                else:
                    present_days += 1
        total = present_days + absent_days
        block.month_marked_days = len(captured)
        block.month_school_days = len(org_working_days(self.db, m.org_id, first, today))
        block.month_pct = round(present_days / total * 100, 1) if total else None

        if not open_today:
            block.headline = "School is closed today."
        elif not block.marked:
            # Never red and never a zero — an unopened register is a state of
            # the record, not news about the children (ux §5).
            block.headline = (f"Not taken yet — {len(roster)} on the roll"
                              + (f", {scheduled} periods scheduled." if scheduled else "."))
        elif not block.absentees:
            block.headline = f"All {len(roster)} in."
            block.tone = "green"
        else:
            n = len(block.absentees)
            block.headline = (f"{n} away of {len(roster)}"
                              + (f" · {block.late} late" if block.late else "") + ".")
            block.tone = "amber" if all(a.explained for a in block.absentees) else "red"
        return block

    def _scheduled_periods(self, m: CurrentMember, klass: SchoolClass, on: date) -> int:
        """How many registers this class is EXPECTED to have today.

        Not how many periods it has — how many the school's mode asks for
        (founder, 2026-08-05). A once-per-day school expects exactly one, and
        reporting "1 of 7 periods marked" there is a screen inventing six
        failures out of a day that was captured exactly as intended.
        """
        if m.org.attendance_mode != "every_period":
            # The mode names its own slots — one for `first_period`, two for
            # `twice_daily`. `every_period` falls through to the timetable,
            # because there the expectation genuinely is "every period this
            # class actually has today", which the grid alone can answer.
            year = self.db.get(AcademicYear, klass.academic_year_id)
            return len(marking_period_nos(
                year.period_times if year else None, m.org.attendance_mode)) or 1
        return int(self.db.scalar(
            select(func.count(func.distinct(TimetableSlot.period_no)))
            .join(ClassSubject, ClassSubject.id == TimetableSlot.class_subject_id)
            .where(TimetableSlot.org_id == m.org_id,
                   ClassSubject.class_id == klass.id,
                   TimetableSlot.weekday == on.weekday(),
                   TimetableSlot.effective_from <= on,
                   (TimetableSlot.effective_to.is_(None))
                   | (TimetableSlot.effective_to >= on))) or 0)

    def _decorate_absentees(self, m: CurrentMember, rows: list[MyClassAbsentee],
                            on: date) -> list[MyClassAbsentee]:
        """Reasons, guardians and today's rail history — four queries for the
        whole list, never one per child. Explained is amber, never red (`D-86`)."""
        if not rows:
            return rows
        ids = [r.student_id for r in rows]
        reasons = {
            sid: (code, note) for sid, code, note in self.db.execute(
                select(AttendanceException.student_id, AttendanceException.reason_code,
                       AttendanceException.reason_note)
                .join(ClassPeriod, ClassPeriod.id == AttendanceException.period_id)
                .where(AttendanceException.org_id == m.org_id,
                       AttendanceException.student_id.in_(ids),
                       AttendanceException.reason_at.is_not(None),
                       ClassPeriod.date == on)).all()
        }
        # An informed-absence note (`S-24`) explains the day just as well as a
        # reason typed on the exception — the school already knows.
        noted = set(self.db.scalars(
            select(StudentAbsenceNote.student_id).where(
                StudentAbsenceNote.org_id == m.org_id,
                StudentAbsenceNote.student_id.in_(ids),
                StudentAbsenceNote.from_date <= on,
                StudentAbsenceNote.to_date >= on).distinct()))
        guardians: dict[uuid.UUID, tuple[str, str | None]] = {}
        for sid, gname, phone, _primary in self.db.execute(
            select(Guardian.student_id, Guardian.name, Guardian.phone, Guardian.is_primary)
            .where(Guardian.student_id.in_(ids))
            .order_by(Guardian.is_primary.desc(), Guardian.created_at)
        ).all():
            guardians.setdefault(sid, (gname, phone))
        done = ActionService(self.db).done_today(m.org_id, "student", on, m.org.timezone)

        for r in rows:
            code, note = reasons.get(r.student_id, (None, None))
            r.reason_code, r.reason_note = code, note
            r.explained = r.student_id in reasons or r.student_id in noted
            gname, gphone = guardians.get(r.student_id, (None, None))
            r.guardian_name, r.guardian_phone = gname, gphone
            r.reminded_today = ("guardian_reminded", r.student_id) in done
            r.tone = "amber" if r.explained else "red"
        rows.sort(key=lambda r: (r.explained, r.full_name))
        return rows

    # ── homework: the V1-17 funnel, for one class ────────────────────────────
    def homework_board(self, m: CurrentMember, class_id: uuid.UUID,
                       days: int = HOMEWORK_WINDOW) -> MyClassHomework:
        self._klass(m, class_id)
        return self._homework_block(m, class_id, today_in(m.org.timezone), days)

    def _homework_block(self, m: CurrentMember, class_id: uuid.UUID, today: date,
                        days: int = HOMEWORK_WINDOW) -> MyClassHomework:
        """`given ⊇ checked ⊇ graded`, in student-homeworks.

        The unit matters and is V1-17's whole correction: counting sets of
        homework in one stage and students in the next puts two units on one
        track. One row here is one child a homework was given to, so the stages
        nest and each gap is a length.

        `not_checked` is the TEACHER's gap: excluded from `completion_pct`,
        never rendered as a child's miss (HW-1). A class nobody has checked must
        not read as a class that did nothing.
        """
        since = today - timedelta(days=max(1, days) - 1)
        out = MyClassHomework(from_date=since, to_date=today)

        roster_size = int(self.db.scalar(
            select(func.count(Student.id)).where(
                Student.org_id == m.org_id, Student.class_id == class_id,
                Student.status == "active")) or 0)

        rows = self.db.execute(
            select(HomeworkAssignment.id, HomeworkAssignment.student_id,
                   HomeworkCheck.id)
            .join(ClassSubject, ClassSubject.id == HomeworkAssignment.class_subject_id)
            .outerjoin(HomeworkCheck, HomeworkCheck.assignment_id == HomeworkAssignment.id)
            .where(HomeworkAssignment.org_id == m.org_id,
                   ClassSubject.class_id == class_id,
                   HomeworkAssignment.date >= since,
                   HomeworkAssignment.date <= today)).all()
        if not rows:
            out.headline = "No homework has been set for this class in this window."
            return out

        checked_ids: list[uuid.UUID] = []
        for aid, student_id, check_id in rows:
            out.assignments += 1
            # A per-student assignment has a roster of exactly one.
            size = roster_size if student_id is None else 1
            out.given += size
            if check_id is None:
                out.not_checked += size
                out.unchecked_assignments += 1
            else:
                out.checked += size
                checked_ids.append(aid)

        verdicts: dict[str, int] = {}
        if checked_ids:
            for status, n in self.db.execute(
                select(HomeworkResult.status, func.count(HomeworkResult.id))
                .join(HomeworkCheck, HomeworkCheck.id == HomeworkResult.check_id)
                .where(HomeworkCheck.assignment_id.in_(checked_ids))
                .group_by(HomeworkResult.status)).all():
                verdicts[status] = int(n)

        exceptions = sum(verdicts.values())
        # Done on time is the ABSENCE of a row (P1v2) — the rest of the checked
        # set. Never a stored count.
        on_time = max(0, out.checked - exceptions)
        out.late = verdicts.get("late", 0)
        out.carried = verdicts.get("carried", 0)
        out.waived = verdicts.get("waived", 0)
        out.missed = verdicts.get("not_done", 0) + verdicts.get("partial", 0)
        # `carried` and `waived` leave the denominator entirely (`D-34`/`S-98`).
        out.graded = max(0, out.checked - out.carried - out.waived)
        out.done_weighted = round(
            on_time + out.late + PARTIAL_WEIGHT * verdicts.get("partial", 0), 1)
        out.completion_pct = (round(out.done_weighted / out.graded * 100, 1)
                              if out.graded else None)

        if out.completion_pct is None:
            out.headline = (f"{out.assignments} "
                            f"{_plural(out.assignments, 'homework')} set and none "
                            "checked yet — there is nothing to report about the "
                            "children until somebody goes through it.")
            out.tone = "neutral"
        else:
            out.headline = (f"{out.completion_pct}% of the {out.graded} checked came "
                            "back done"
                            + (f", {out.late} of them late" if out.late else "")
                            + (f" · {out.unchecked_assignments} "
                               f"{_plural(out.unchecked_assignments, 'homework')} "
                               "still unchecked." if out.unchecked_assignments else "."))
            out.tone = ("green" if out.completion_pct >= 85
                        else "amber" if out.completion_pct >= 70 else "red")
        return out

    # ── the day book: what actually went home (founder, 2026-08-05) ──────────
    def homework_days(self, m: CurrentMember, class_id: uuid.UUID, page: int = 1,
                      size: int = 20) -> MyClassHomeworkDays:
        """Today in full, every earlier day as a row.

        Paginated over DAYS. The window is deliberately the whole year rather
        than the funnel's fortnight: the funnel answers "how are we doing", this
        answers "what went home on the 14th", and that question is asked about
        dates long past the fortnight.
        """
        klass = self._klass(m, class_id)
        today = today_in(m.org.timezone)
        size = min(max(size, 1), 100)
        page = max(page, 1)

        roster_size = int(self.db.scalar(
            select(func.count(Student.id)).where(
                Student.org_id == m.org_id, Student.class_id == class_id,
                Student.status == "active")) or 0)

        # Every day this class was set homework, newest first. One query, and it
        # is the pagination key — assignments per day vary from one to six and
        # paging on them would cut a day in half.
        days = [d for (d,) in self.db.execute(
            select(HomeworkAssignment.date)
            .join(ClassSubject, ClassSubject.id == HomeworkAssignment.class_subject_id)
            .where(HomeworkAssignment.org_id == m.org_id,
                   ClassSubject.class_id == class_id)
            .group_by(HomeworkAssignment.date)
            .order_by(HomeworkAssignment.date.desc())).all()]

        # Today is shown in full above the table and is never also a row in it —
        # the same day in two places invites the reader to compare them.
        past = [d for d in days if d != today]
        window = past[(page - 1) * size: page * size]

        rows = self._day_rows(m, class_id, window, roster_size) if window else []
        today_items = (self._day_items(m, class_id, today, roster_size)
                       if today in days else [])

        out = MyClassHomeworkDays(
            class_id=class_id, class_label=_label(klass), today=today,
            today_items=today_items, rows=rows, page=page, size=size,
            total_days=len(past))
        if today_items:
            n = len(today_items)
            subjects = sorted({i.subject_name for i in today_items})
            out.headline = (f"{n} {_plural(n, 'homework')} went home today — "
                            + ", ".join(subjects) + ".")
        elif days:
            out.headline = ("Nothing has been set today. The last homework for "
                            f"this class was on {days[0]}.")
        else:
            out.headline = "No homework has ever been recorded for this class."
        return out

    def homework_day(self, m: CurrentMember, class_id: uuid.UUID,
                     on: date) -> MyClassHomeworkDay:
        """One day, opened — every homework in full, with who did not do it."""
        klass = self._klass(m, class_id)
        roster_size = int(self.db.scalar(
            select(func.count(Student.id)).where(
                Student.org_id == m.org_id, Student.class_id == class_id,
                Student.status == "active")) or 0)
        items = self._day_items(m, class_id, on, roster_size)
        day = self._roll_up(on, items)
        if not items:
            headline = "No homework was set for this class on that day."
        elif day.completion_pct is None:
            headline = (f"{day.assignments} {_plural(day.assignments, 'homework')} "
                        "set, and none of it has been gone through — so there is "
                        "nothing to report about the children yet.")
        else:
            headline = (f"{day.completion_pct}% of the {day.graded} checked came "
                        "back done"
                        + (f", {day.late} of them late" if day.late else "")
                        + (f" · {day.unchecked_assignments} still unchecked."
                           if day.unchecked_assignments else "."))
        return MyClassHomeworkDay(
            class_id=class_id, class_label=_label(klass), date=on, day=day,
            items=items, headline=headline)

    def _day_items(self, m: CurrentMember, class_id: uuid.UUID, on: date,
                   roster_size: int) -> list[HomeworkItem]:
        """Every homework set on one day, with its verdicts. Four queries."""
        rows = self.db.execute(
            select(HomeworkAssignment, Subject.name, Subject.id, User.name,
                   HomeworkCheck)
            .join(ClassSubject, ClassSubject.id == HomeworkAssignment.class_subject_id)
            .join(Subject, Subject.id == ClassSubject.subject_id)
            .outerjoin(Membership, Membership.id == ClassSubject.teacher_member_id)
            .outerjoin(User, User.id == Membership.user_id)
            .outerjoin(HomeworkCheck, HomeworkCheck.assignment_id == HomeworkAssignment.id)
            .where(HomeworkAssignment.org_id == m.org_id,
                   ClassSubject.class_id == class_id,
                   HomeworkAssignment.date == on)
            .order_by(Subject.name, HomeworkAssignment.created_at)).all()
        if not rows:
            return []

        aids = [a.id for a, *_ in rows]
        # The exception rows, with the child's name — this list IS the record of
        # who did not do it, because doing it on time writes nothing (P1v2).
        results: dict[uuid.UUID, list[HomeworkMissRow]] = defaultdict(list)
        for aid, sid, status, note, name, roll in self.db.execute(
            select(HomeworkResult.assignment_id, HomeworkResult.student_id,
                   HomeworkResult.status, HomeworkResult.note,
                   Student.full_name, Student.roll_no)
            .join(Student, Student.id == HomeworkResult.student_id)
            .where(HomeworkResult.org_id == m.org_id,
                   HomeworkResult.assignment_id.in_(aids))
            .order_by(Student.full_name)).all():
            results[aid].append(HomeworkMissRow(
                student_id=sid, full_name=name, roll_no=roll, status=status,
                note=note))

        personal = {a.student_id for a, *_ in rows if a.student_id}
        names = dict(self.db.execute(
            select(Student.id, Student.full_name)
            .where(Student.id.in_(personal))).all()) if personal else {}
        checkers = dict(self.db.execute(
            select(Membership.id, User.name).join(User, User.id == Membership.user_id)
            .where(Membership.id.in_(
                {c.checked_by_member_id for *_x, c in rows
                 if c is not None and c.checked_by_member_id}))).all())

        out: list[HomeworkItem] = []
        for a, subject_name, subject_id, teacher_name, check in rows:
            item = HomeworkItem(
                assignment_id=a.id, date=a.date, class_subject_id=a.class_subject_id,
                subject_id=subject_id, subject_name=subject_name,
                teacher_name=teacher_name, text=a.text, due_date=a.due_date,
                student_id=a.student_id,
                student_name=names.get(a.student_id) if a.student_id else None,
                # A personal addition has a roster of exactly one.
                given=1 if a.student_id else roster_size,
                checked=check is not None,
                checked_at=check.checked_at if check is not None else None,
                checked_by_name=(checkers.get(check.checked_by_member_id)
                                 if check is not None else None))
            if check is not None:
                misses = results.get(a.id, [])
                item.misses = misses
                counts = tally([r.status for r in misses])
                item.late = counts.get("late", 0)
                item.partial = counts.get("partial", 0)
                item.not_done = counts.get("not_done", 0)
                item.carried = counts.get("carried", 0)
                item.waived = counts.get("waived", 0)
                # Done on time is the ABSENCE of a row; carried and waived leave
                # the denominator entirely (`D-34`/`S-98`).
                item.graded = max(0, item.given - item.carried - item.waived)
                on_time = max(0, item.given - len(misses))
                item.done = on_time + item.late
                weighted = on_time + item.late + PARTIAL_WEIGHT * item.partial
                item.completion_pct = (round(weighted / item.graded * 100, 1)
                                       if item.graded else None)
            out.append(item)
        return out

    def _day_rows(self, m: CurrentMember, class_id: uuid.UUID, days: list[date],
                  roster_size: int) -> list[HomeworkDayRow]:
        """The table's rows. One pass over the page's days, not one query each."""
        rows = self.db.execute(
            select(HomeworkAssignment.id, HomeworkAssignment.date,
                   HomeworkAssignment.student_id, Subject.name, HomeworkCheck.id)
            .join(ClassSubject, ClassSubject.id == HomeworkAssignment.class_subject_id)
            .join(Subject, Subject.id == ClassSubject.subject_id)
            .outerjoin(HomeworkCheck, HomeworkCheck.assignment_id == HomeworkAssignment.id)
            .where(HomeworkAssignment.org_id == m.org_id,
                   ClassSubject.class_id == class_id,
                   HomeworkAssignment.date.in_(days))).all()
        verdicts: dict[uuid.UUID, dict[str, int]] = defaultdict(dict)
        aids = [r[0] for r in rows]
        if aids:
            for aid, status, n in self.db.execute(
                select(HomeworkResult.assignment_id, HomeworkResult.status,
                       func.count(HomeworkResult.id))
                .where(HomeworkResult.org_id == m.org_id,
                       HomeworkResult.assignment_id.in_(aids))
                .group_by(HomeworkResult.assignment_id, HomeworkResult.status)).all():
                verdicts[aid][status] = int(n)

        by_day: dict[date, HomeworkDayRow] = {
            d: HomeworkDayRow(date=d) for d in days}
        subjects: dict[date, set[str]] = defaultdict(set)
        weighted: dict[date, float] = defaultdict(float)
        for aid, d, student_id, subject_name, check_id in rows:
            row = by_day[d]
            row.assignments += 1
            subjects[d].add(subject_name)
            given = 1 if student_id else roster_size
            row.given += given
            if check_id is None:
                row.not_checked += given
                row.unchecked_assignments += 1
                continue
            row.checked += given
            v = verdicts.get(aid, {})
            late = v.get("late", 0)
            partial = v.get("partial", 0)
            not_done = v.get("not_done", 0)
            carried = v.get("carried", 0)
            waived = v.get("waived", 0)
            exceptions = late + partial + not_done + carried + waived
            on_time = max(0, given - exceptions)
            graded = max(0, given - carried - waived)
            row.graded += graded
            row.late += late
            row.missed += not_done + partial
            weighted[d] += on_time + late + PARTIAL_WEIGHT * partial

        out: list[HomeworkDayRow] = []
        for d in days:
            row = by_day[d]
            row.subjects = sorted(subjects[d])
            row.done_weighted = round(weighted[d], 1)
            row.completion_pct = (round(weighted[d] / row.graded * 100, 1)
                                  if row.graded else None)
            row.tone = self._hw_tone(row.completion_pct)
            out.append(row)
        return out

    @staticmethod
    def _hw_tone(pct: float | None) -> str:
        """A day nobody checked is NEUTRAL, never red — HW-1's rule, and the one
        thing this table could most easily get wrong at a glance."""
        if pct is None:
            return "neutral"
        return "green" if pct >= 85 else "amber" if pct >= 70 else "red"

    @staticmethod
    def _roll_up(on: date, items: list[HomeworkItem]) -> HomeworkDayRow:
        row = HomeworkDayRow(date=on, assignments=len(items),
                             subjects=sorted({i.subject_name for i in items}))
        weighted = 0.0
        for i in items:
            row.given += i.given
            if not i.checked:
                row.not_checked += i.given
                row.unchecked_assignments += 1
                continue
            row.checked += i.given
            row.graded += i.graded
            row.late += i.late
            row.missed += i.not_done + i.partial
            on_time = i.done - i.late
            weighted += on_time + i.late + PARTIAL_WEIGHT * i.partial
        row.done_weighted = round(weighted, 1)
        row.completion_pct = (round(weighted / row.graded * 100, 1)
                              if row.graded else None)
        row.tone = MyClassService._hw_tone(row.completion_pct)
        return row

    # ── the support tiers, per subject ───────────────────────────────────────
    def bands_board(self, m: CurrentMember, class_id: uuid.UUID) -> MyClassBands:
        klass = self._klass(m, class_id)
        return self._bands_block(m, self._class_roster(m, class_id),
                                 klass=klass, with_students=True)

    def _bands_block(self, m: CurrentMember, roster: list[Student],
                     klass: SchoolClass | None = None,
                     with_students: bool = False) -> MyClassBands:
        """A/B/C per MONITORED subject, for this class.

        The unit is the PLACEMENT, not the child (`D-75`) — there is no overall
        letter, so a boy who is A in Maths and C in Hindi is counted in both
        columns. `not_assessed` is its own number in its own word and is never a
        tier: a child who has not sat the test is not a C.
        """
        out = MyClassBands()
        bands = BandService(self.db)
        monitored = bands.monitored_subjects(m)
        out.monitored = len(monitored)
        if not monitored or not roster:
            out.headline = ("No subject is on the support programme yet."
                            if not monitored else "No children on the roll.")
            return out

        ids = [s.id for s in roster]
        placements = bands.placements(m, ids)

        # Expanded, the subject names its children and says how each is doing in
        # THAT subject — the one figure a band is supposed to be about. Loaded
        # only for the tab; the Overview's block is counts and does not pay for
        # it. Both are batched reads, four queries and one walk, not per child.
        marks = attendance = None
        if with_students and klass is not None and ids:
            marks = load_class_marks(self.db, m.org_id, klass.id, ids)
            attendance, _captured, _away = self._attendance_window(
                m, klass, roster, today_in(m.org.timezone), STUDENT_WINDOW)

        for subject in monitored:
            row = MyClassBandSubject(subject_id=subject.id, subject_name=subject.name)
            for s in roster:
                tier = next((p.tier for p in placements.get(s.id, [])
                             if p.subject_id == subject.id), None)
                if tier == "A":
                    row.a += 1
                elif tier == "B":
                    row.b += 1
                elif tier == "C":
                    row.c += 1
                else:
                    # Not a tier and never rendered as one — only the
                    # denominator beside "assessed" (`D-75`).
                    row.not_assessed += 1
                    continue
                if not with_students:
                    continue
                row.students.append(self._band_student(
                    s, tier, subject.id, marks, attendance))
            # A band is a teaching group, so the list reads A → B → C and by
            # name inside a tier: never ordered by the percentage, which would
            # make it a ranking of children (`S-170`).
            row.students.sort(key=lambda r: ("ABC".index(r.tier), r.full_name))
            row.assessed = row.a + row.b + row.c
            out.subjects.append(row)

        total_c = sum(r.c for r in out.subjects)
        assessed = sum(r.assessed for r in out.subjects)
        if not assessed:
            out.headline = ("Nobody in this class has been assessed for a band yet.")
        else:
            worst = max(out.subjects, key=lambda r: r.c)
            out.headline = (
                f"{total_c} {_plural(total_c, 'placement')} in band C across "
                f"{out.monitored} monitored {_plural(out.monitored, 'subject')}"
                + (f", most of them in {worst.subject_name}." if worst.c else "."))
        return out

    @staticmethod
    def _band_student(s: Student, tier: str, subject_id: uuid.UUID,
                      marks, attendance) -> MyClassBandStudent:
        """One child under a tier, with how they are actually doing in it.

        The figure is `ClassMarks.figures`' — the school's marks read through
        `core/exams.py`, which refuses to pool a slip test with a term paper. So
        the row carries the **scale its percentage came from**, and prefers the
        major one where both exist: standing is read from major, trajectory from
        minor, and a bare blended number is the one thing that module exists to
        make un-writable. Nothing recorded is null, never 0.
        """
        row = MyClassBandStudent(
            student_id=s.id, full_name=s.full_name, roll_no=s.roll_no, tier=tier)
        if attendance is not None:
            row.attendance_pct = attendance.get(s.id, (None, 0, 0))[0]
        if marks is None:
            return row
        figures = [f for f in marks.figures(s.id, subject_id) if f.tests_held]
        if not figures:
            return row
        best = next((f for f in figures if f.scale == "major" and f.tests_taken), None) \
            or next((f for f in figures if f.tests_taken), figures[0])
        row.scale = best.scale
        row.pct = best.pct
        row.tests_taken = best.tests_taken
        row.tests_held = best.tests_held
        row.sentence = best.sentence()
        return row

    # ── exams ────────────────────────────────────────────────────────────────
    def _exams_block(self, m: CurrentMember, class_id: uuid.UUID) -> MyClassExams:
        """The last few exams, read from `ExamService.feed` verbatim.

        Minor and major are never pooled (`core/exams.py`), so the headline
        speaks about ONE exam rather than averaging a slip test into a term
        paper — there is deliberately no blended figure here to quote.
        """
        out = MyClassExams()
        feed = ExamService(self.db).feed(m, class_id=class_id, limit=EXAM_FEED_LIMIT)
        out.recent = [e.model_dump(mode="json") for e in feed]
        rated = [e for e in feed if e.avg_pct is not None]
        if not rated:
            out.headline = ("No exam has been recorded for this class yet."
                            if not feed else
                            f"{len(feed)} {_plural(len(feed), 'exam')} recorded, "
                            "none with marks entered yet.")
            return out
        latest = rated[0]
        out.headline = (
            f"{latest.name} — {latest.avg_pct}% average across "
            f"{latest.scored_count} of {latest.roster_count} children"
            + (f" ({latest.type_label})." if latest.type_label else "."))
        return out

    # ── the syllabus, all subjects ───────────────────────────────────────────
    def _syllabus_block(self, m: CurrentMember, class_id: uuid.UUID) -> dict | None:
        """`MySyllabusService.class_syllabus` verbatim (`D-15`/`S-28`).

        Not a second shape and not a second computation: the pace comes from
        `PlannerService.forecast_org` and the coverage from `CoverageReader`,
        which is exactly what the admin board reads.
        """
        try:
            return MySyllabusService(self.db).class_syllabus(m, class_id).model_dump(
                mode="json")
        except (ForbiddenError, NotFoundError):
            # An admin browsing a class they do not own still gets the rest of
            # the board rather than a 403 for the whole page.
            return None

    def syllabus_board(self, m: CurrentMember, class_id: uuid.UUID,
                       term_id: uuid.UUID | None = None):
        """The SY-1 chapter table, for every subject this class takes.

        The same `SyllabusBoardService.board` the Plan tab renders — chapter by
        chapter, with planned dates, the frozen baseline, pace and the status
        word — and not a second, thinner shape of it. The per-subject pace list
        the Overview carries answers *"is Maths moving?"*; a class teacher asked
        for a chapter also needs to know **which** chapter and when it was due,
        and that is a table.

        `whole_class=True` is safe here and only here: `_klass` has already
        established this is her homeroom (or that she is an admin), which is
        exactly the fact Plan → Syllabus deliberately no longer reads.
        """
        klass = self._klass(m, class_id)
        return SyllabusBoardService(self.db).board(
            m, klass.academic_year_id, class_id=class_id, term_id=term_id,
            whole_class=True)

    # ── the roster as a table, each row a door into a child's file ───────────
    def students(self, m: CurrentMember, class_id: uuid.UUID,
                 days: int = STUDENT_WINDOW) -> MyClassStudentsOut:
        """Every child, with the four figures a class teacher scans for.

        Deliberately NOT a ranking, and every figure carries its own
        denominator: an unmarked attendance denominator or an unchecked homework
        denominator is `None`, never 0 — a class nobody captured must not read
        as a class of absentees, and a homework nobody checked must not read as
        a child who did not do it (HW-1).
        """
        klass = self._klass(m, class_id)
        today = today_in(m.org.timezone)
        since = today - timedelta(days=max(1, days) - 1)
        roster = self._class_roster(m, class_id)
        out = MyClassStudentsOut(class_id=class_id, class_label=_label(klass),
                                 from_date=since, to_date=today)
        if not roster:
            out.headline = "Nobody is on this class's roll yet."
            return out

        ids = [s.id for s in roster]
        att, captured, absent_today = self._attendance_window(
            m, klass, roster, today, days)

        homework = self._student_homework(m, class_id, ids, since, today)
        placements = BandService(self.db).placements(m, ids)
        latest = self._latest_exam(m, ids)
        notes = dict(self.db.execute(
            select(StudentNote.student_id, func.count(StudentNote.id))
            .where(StudentNote.org_id == m.org_id, StudentNote.student_id.in_(ids))
            .group_by(StudentNote.student_id)).all())
        guardians: dict[uuid.UUID, tuple[str, str | None]] = {}
        for sid, gname, phone, _p in self.db.execute(
            select(Guardian.student_id, Guardian.name, Guardian.phone, Guardian.is_primary)
            .where(Guardian.student_id.in_(ids))
            .order_by(Guardian.is_primary.desc(), Guardian.created_at)).all():
            guardians.setdefault(sid, (gname, phone))
        categories = dict(self.db.execute(
            select(StudentCategory.id, StudentCategory.name)
            .where(StudentCategory.org_id == m.org_id)).all())

        for s in roster:
            pct, md, absent = att.get(s.id, (None, 0, 0))
            hw = homework.get(s.id)
            gname, gphone = guardians.get(s.id, (None, None))
            # The chip is "C · Hindi" (`S-186`) — the lowest band with the
            # subject that earned it, never a bare letter and never an average.
            chips = [f"{p.tier} · {p.subject_name}"
                     for p in sorted(placements.get(s.id, []),
                                     key=lambda p: ("ABC".index(p.tier)
                                                    if p.tier in "ABC" else 9))]
            exam = latest.get(s.id)
            out.rows.append(MyClassStudentRow(
                student_id=s.id, full_name=s.full_name, roll_no=s.roll_no,
                admission_no=s.admission_no,
                category=categories.get(s.category_id) if s.category_id else None,
                attendance_pct=pct, marked_days=md, days_absent=absent,
                absent_today=s.id in absent_today,
                homework_pct=hw[0] if hw else None,
                homework_missed=hw[1] if hw else 0,
                homework_graded=hw[2] if hw else 0,
                band_chips=chips,
                latest_exam_pct=exam[0] if exam else None,
                latest_exam_name=exam[1] if exam else None,
                note_count=int(notes.get(s.id, 0)),
                guardian_name=gname, guardian_phone=gphone,
                # Amber, never red, and only on evidence that EXISTS: a child
                # with nothing captured is neutral, not a concern.
                tone=("red" if (pct is not None and pct < 75)
                      or (hw and hw[0] is not None and hw[0] < 50)
                      else "amber" if (pct is not None and pct < 90)
                      or (hw and hw[0] is not None and hw[0] < 75)
                      else "neutral")))

        rated = [r for r in out.rows if r.attendance_pct is not None]
        if rated:
            avg = round(sum(r.attendance_pct for r in rated) / len(rated), 1)
            out.headline = (f"{len(out.rows)} children · {avg}% average attendance "
                            f"across the {len(captured)} "
                            f"{_plural(len(captured), 'day')} this class marked.")
        else:
            out.headline = (f"{len(out.rows)} children · nothing has been marked for "
                            "this class in the window, so there is no attendance "
                            "figure to show.")
        return out

    def _attendance_window(self, m: CurrentMember, klass: SchoolClass,
                           roster: list[Student], today: date, days: int,
                           ) -> tuple[dict[uuid.UUID, tuple[float | None, int, int]],
                                      list[date], set[uuid.UUID]]:
        """student → (attendance %, marked days, days absent), over `days`.

        Extracted so the roster table and the band tiers read ONE walk of the
        register rather than each writing their own — the `S-51` rule at the
        smallest scale it still matters at, since two lists on two tabs quoting
        different attendance for the same child is exactly the defect.

        The denominator is the days THIS class marked, and a child with nothing
        captured gets `None`, never 0: a class nobody took the register for must
        not read as a class of absentees.
        """
        since = today - timedelta(days=max(1, days) - 1)
        year = self.db.get(AcademicYear, klass.academic_year_id)
        marking = marking_period_nos(
            year.period_times if year else None, m.org.attendance_mode)
        marked, exc = day_matrix(self.db, m.org_id, [klass.id], since, today)
        captured = sorted({d for (_c, d) in marked if marked[(_c, d)]})

        absent_days: dict[uuid.UUID, int] = defaultdict(int)
        marked_days: dict[uuid.UUID, int] = defaultdict(int)
        absent_today: set[uuid.UUID] = set()
        for d in captured:
            periods = marked.get((klass.id, d), [])
            for s in roster:
                # `S-02`: a mid-year joiner's denominator starts at enrolment.
                if s.enrolled_on and d < s.enrolled_on:
                    continue
                per = exc.get((s.id, d), {})
                status, _l = classify_marked_day(
                    periods, {p: st for p, (st, _r) in per.items()}, marking)
                marked_days[s.id] += 1
                if status == "absent":
                    absent_days[s.id] += 1
                    if d == today:
                        absent_today.add(s.id)

        out: dict[uuid.UUID, tuple[float | None, int, int]] = {}
        for s in roster:
            md = marked_days.get(s.id, 0)
            absent = absent_days.get(s.id, 0)
            out[s.id] = (round((md - absent) / md * 100, 1) if md else None,
                         md, absent)
        return out, captured, absent_today

    def _student_homework(self, m: CurrentMember, class_id: uuid.UUID,
                          ids: list[uuid.UUID], since: date, today: date,
                          ) -> dict[uuid.UUID, tuple[float | None, int, int]]:
        """student → (completion %, misses, graded count) over the window.

        Two queries. Done on time is the absence of a row, so the graded count
        starts from the CHECKED assignments each child was given and the
        exception rows subtract from it — `carried`/`waived` leaving the
        denominator, `not_checked` never entering it.
        """
        if not ids:
            return {}
        checked = self.db.execute(
            select(HomeworkAssignment.id, HomeworkAssignment.student_id)
            .join(ClassSubject, ClassSubject.id == HomeworkAssignment.class_subject_id)
            .join(HomeworkCheck, HomeworkCheck.assignment_id == HomeworkAssignment.id)
            .where(HomeworkAssignment.org_id == m.org_id,
                   ClassSubject.class_id == class_id,
                   HomeworkAssignment.date >= since,
                   HomeworkAssignment.date <= today)).all()
        if not checked:
            return {}
        given: dict[uuid.UUID, int] = defaultdict(int)
        check_ids = []
        for aid, student_id in checked:
            check_ids.append(aid)
            if student_id is None:
                for sid in ids:
                    given[sid] += 1
            elif student_id in ids:
                given[student_id] += 1

        weight: dict[uuid.UUID, float] = defaultdict(float)
        drop: dict[uuid.UUID, int] = defaultdict(int)
        misses: dict[uuid.UUID, int] = defaultdict(int)
        for sid, status, n in self.db.execute(
            select(HomeworkResult.student_id, HomeworkResult.status,
                   func.count(HomeworkResult.id))
            .join(HomeworkCheck, HomeworkCheck.id == HomeworkResult.check_id)
            .where(HomeworkCheck.assignment_id.in_(check_ids),
                   HomeworkResult.student_id.in_(ids))
            .group_by(HomeworkResult.student_id, HomeworkResult.status)).all():
            n = int(n)
            if status in ("carried", "waived"):
                drop[sid] += n           # leaves the denominator entirely
                continue
            # Every exception row replaces an assumed on-time 1.0 with its own
            # weight; `late` is worth a full 1.0 and is reported beside, never
            # inside, the figure (`S-99`).
            weight[sid] += verdict_weight(status) or 0.0
            weight[sid] -= 1.0
            if is_miss(status):
                misses[sid] += n

        out: dict[uuid.UUID, tuple[float | None, int, int]] = {}
        for sid in ids:
            graded = given.get(sid, 0) - drop.get(sid, 0)
            if graded <= 0:
                out[sid] = (None, misses.get(sid, 0), 0)
                continue
            done = max(0.0, graded + weight.get(sid, 0.0))
            out[sid] = (round(done / graded * 100, 1), misses.get(sid, 0), graded)
        return out

    def _latest_exam(self, m: CurrentMember, ids: list[uuid.UUID],
                     ) -> dict[uuid.UUID, tuple[float | None, str]]:
        """student → (percentage, exam name) for their most recent scored exam.

        One row per child, from the newest cycle they actually sat — never an
        average across scales (`core/exams.py`: minor and major do not pool).
        """
        if not ids:
            return {}
        out: dict[uuid.UUID, tuple[float | None, str]] = {}
        for sid, score, max_score, name in self.db.execute(
            select(AssessmentScore.student_id, AssessmentScore.score,
                   AssessmentScore.max_score, AssessmentCycle.name)
            .join(AssessmentCycle, AssessmentCycle.id == AssessmentScore.cycle_id)
            .where(AssessmentScore.student_id.in_(ids))
            .order_by(AssessmentCycle.date.desc(),
                      AssessmentCycle.created_at.desc())).all():
            if sid in out:
                continue
            pct = (round(float(score) / float(max_score) * 100, 1)
                   if score is not None and max_score else None)
            out[sid] = (pct, name)
        return out

    # ── the class teacher's own log about a child ────────────────────────────
    def _student(self, m: CurrentMember, student_id: uuid.UUID) -> Student:
        student = self.db.scalar(select(Student).where(
            Student.id == student_id, Student.org_id == m.org_id))
        if student is None:
            raise NotFoundError("Student")
        return student

    def _can_log(self, m: CurrentMember, student: Student) -> bool:
        """Who may WRITE a note: an admin, the class teacher of this child, or
        the teacher who **owns his support plan** (founder 2026-08-05).

        Still deliberately narrower than reading. A subject teacher has the deep
        log (`lesson_observations`) for what happens in her lesson; this is the
        running account of a child, and it is only a record if it has few
        authors. The support owner is the third because she is the person the
        school has made responsible for him — and the ABC bands area now asks
        her for exactly this, both against an assessment and at any time.
        """
        if m.is_admin:
            return True
        if student.class_id is not None and self.db.scalar(select(SchoolClass.id).where(
                SchoolClass.id == student.class_id, SchoolClass.org_id == m.org_id,
                SchoolClass.class_teacher_member_id == m.membership.id)) is not None:
            return True
        return self.db.scalar(select(Intervention.id).where(
            Intervention.org_id == m.org_id,
            Intervention.student_id == student.id,
            Intervention.owner_member_id == m.membership.id,
            Intervention.status == "active").limit(1)) is not None

    def notes(self, m: CurrentMember, student_id: uuid.UUID) -> StudentNotesOut:
        student = self._student(m, student_id)
        can_write = self._can_log(m, student)
        # Reading is open to the staff already trusted with this child (the same
        # rule the growth report uses); writing is narrower. Anyone allowed to
        # WRITE can obviously read — which is what lets a support owner outside
        # the class open her own child's log rather than being able to add to a
        # record she cannot see.
        if not m.is_admin and not can_write and student.class_id is not None:
            allowed = visible_class_ids(self.db, m)
            if allowed is not None and student.class_id not in allowed:
                raise ForbiddenError("That is not your student.",
                                     code="not_your_student")
        rows = list(self.db.scalars(
            select(StudentNote).where(
                StudentNote.org_id == m.org_id,
                StudentNote.student_id == student_id)
            .order_by(StudentNote.created_at.desc()).limit(MAX_NOTES)))
        authors = {
            mid: name for mid, name in self.db.execute(
                select(Membership.id, User.name)
                .join(User, User.id == Membership.user_id)
                .where(Membership.id.in_(
                    {r.author_member_id for r in rows if r.author_member_id})))
        } if rows else {}
        return StudentNotesOut(
            student_id=student_id, full_name=student.full_name,
            can_write=can_write,
            rows=[StudentNoteOut(
                id=r.id, student_id=r.student_id, kind=r.kind, note=r.note,
                assessment_id=r.assessment_id,
                author_name=authors.get(r.author_member_id),
                created_at=r.created_at) for r in rows])

    def add_note(self, m: CurrentMember, student_id: uuid.UUID,
                 body: StudentNoteIn) -> StudentNotesOut:
        """Append-only (law 3). There is no edit and no delete: what a teacher
        thought in September is part of the record when November disagrees, and
        a log that can be quietly rewritten is not a log."""
        student = self._student(m, student_id)
        if not self._can_log(m, student):
            raise ForbiddenError("Only this child's class teacher can add to the log.",
                                 code="not_your_student")
        self.db.add(StudentNote(
            org_id=m.org_id, student_id=student_id, kind=body.kind,
            note=body.note.strip(), assessment_id=body.assessment_id,
            author_member_id=m.membership.id))
        self.db.flush()
        return self.notes(m, student_id)
