"""My Class — the class teacher's area (V1-3, D-03).

Centred on the month attendance grid: student × school day, each cell THE day
status from `classify_marked_day` (ux §9 — the same classifier the admin board
and the parent strip render). A row's shape says "every Monday" or "a block in
October" or "slowly fading" faster than any percentage.

Access: the class teacher of THIS class, or an admin. Another teacher gets 403 —
her children are the point of the assignment.
"""

import uuid
from calendar import monthrange
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.exceptions import ForbiddenError, NotFoundError
from app.models import (
    AcademicYear,
    CalendarEvent,
    SchoolClass,
    Student,
    StudentAbsenceNote,
)
from app.schemas.my_class import (
    MyClassOut,
    MyClassSummary,
    RegisterCell,
    RegisterOut,
    RegisterRow,
)
from app.services.attendance import classify_marked_day, day_matrix
from app.services.calendar import event_rows, expand_blocked_dates
from app.services.school_clock import marking_period_nos, today_in

# Day statuses that mean "the child was in school at some point".
PRESENT_STATUSES = ("present", "partial", "left_after_lunch")


def _label(klass: SchoolClass) -> str:
    return klass.name + (f"-{klass.section}" if klass.section else "")


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

    def register(self, m: CurrentMember, class_id: uuid.UUID,
                 month: str | None = None) -> RegisterOut:
        """The month grid. `month` = "YYYY-MM"; defaults to the current month.
        Cells stop at today — the future is blank, not a state."""
        klass = self.db.scalar(select(SchoolClass).where(
            SchoolClass.id == class_id, SchoolClass.org_id == m.org_id))
        if klass is None:
            raise NotFoundError("Class")
        self._guard(m, klass)

        today = today_in(m.org.timezone)
        if month:
            try:
                y, mo = int(month[:4]), int(month[5:7])
                first = date(y, mo, 1)
            except (ValueError, IndexError):
                first = today.replace(day=1)
        else:
            first = today.replace(day=1)
        last = min(date(first.year, first.month,
                        monthrange(first.year, first.month)[1]), today)

        year = self.db.get(AcademicYear, klass.academic_year_id)
        working = set(year.working_weekdays or [0, 1, 2, 3, 4, 5]) if year \
            else {0, 1, 2, 3, 4, 5}
        blocked = expand_blocked_dates(event_rows(self.db.scalars(
            select(CalendarEvent).where(
                CalendarEvent.org_id == m.org_id,
                CalendarEvent.academic_year_id == klass.academic_year_id,
                CalendarEvent.end_date >= first, CalendarEvent.start_date <= last))))
        marking = marking_period_nos(
            year.period_times if year else None, m.org.attendance_mode)
        days = [d for d in (date.fromordinal(o)
                            for o in range(first.toordinal(), last.toordinal() + 1))
                if d.weekday() in working and d not in blocked] if last >= first else []

        roster = list(self.db.scalars(
            select(Student).where(
                Student.org_id == m.org_id, Student.class_id == class_id,
                Student.status == "active").order_by(Student.full_name)))
        marked, exc = day_matrix(self.db, m.org_id, [class_id], first, last)

        # Covering informed-absence notes for the window (S-24): explained days.
        noted: dict[uuid.UUID, list[tuple[date, date]]] = {}
        for n in self.db.scalars(select(StudentAbsenceNote).where(
                StudentAbsenceNote.org_id == m.org_id,
                StudentAbsenceNote.student_id.in_([s.id for s in roster]),
                StudentAbsenceNote.from_date <= last,
                StudentAbsenceNote.to_date >= first)):
            noted.setdefault(n.student_id, []).append((n.from_date, n.to_date))

        rows: list[RegisterRow] = []
        for s in roster:
            cells: list[RegisterCell] = []
            present_days = marked_days = 0
            since = s.enrolled_on  # S-02: a joiner's denominator starts here
            for d in days:
                if since and d < since:
                    cells.append(RegisterCell(date=d, status="no_school"))
                    continue
                periods = marked.get((class_id, d))
                if not periods:
                    cells.append(RegisterCell(date=d, status="not_marked"))
                    continue
                per = exc.get((s.id, d), {})
                status, late = classify_marked_day(
                    periods, {p: st for p, (st, _r) in per.items()}, marking)
                has_reason = any(r for _st, r in per.values()) or any(
                    a <= d <= b for a, b in noted.get(s.id, []))
                marked_days += 1
                if status in PRESENT_STATUSES:
                    present_days += 1
                cells.append(RegisterCell(
                    date=d, status=status, late=late, has_reason=has_reason))
            rows.append(RegisterRow(
                student_id=s.id, full_name=s.full_name, roll_no=s.roll_no,
                cells=cells, present_days=present_days, marked_days=marked_days))

        return RegisterOut(
            class_id=class_id, class_label=_label(klass),
            month=f"{first.year:04d}-{first.month:02d}",
            mode=m.org.attendance_mode, days=days, rows=rows,
            school_days=len(days))
