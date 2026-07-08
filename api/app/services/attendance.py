"""Per-period attendance (V2-M4, SPRD2 §5.4) — capture-by-exception.

"All present ✓" writes one `attendance_marks` row for the class-period; the teacher
taps only deviations, which become `attendance_exceptions` (absent | late). Present
is derived: roster minus absentees (late students are present-but-flagged).

The day's FIRST marked period for a class fires guardian absence alerts (§7) once —
`alerted_at` on that mark makes it idempotent across re-marks/edits. Alerts carry
plain "absent today" text only; never band/tier info (P4).
"""

import uuid
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.context import CurrentMember
from app.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.models import (
    AttendanceException,
    AttendanceMark,
    ClassSubject,
    Guardian,
    SchoolClass,
    Student,
)
from app.schemas.attendance import (
    AttendanceMarkIn,
    AttendanceMarkOut,
    AttendanceRosterOut,
    AttendanceRosterRow,
)
from app.services.notify_guardian import notify_guardians


def _label(klass: SchoolClass) -> str:
    return klass.name + (f"-{klass.section}" if klass.section else "")


class AttendanceService:
    def __init__(self, db: Session):
        self.db = db

    def _today(self, m: CurrentMember) -> date:
        return datetime.now(ZoneInfo(m.org.timezone)).date()

    def _class(self, org_id: uuid.UUID, class_id: uuid.UUID) -> SchoolClass:
        klass = self.db.scalar(
            select(SchoolClass).where(SchoolClass.id == class_id, SchoolClass.org_id == org_id))
        if klass is None:
            raise NotFoundError("Class")
        return klass

    def _can_mark(self, m: CurrentMember, class_id: uuid.UUID,
                  class_subject_id: uuid.UUID | None) -> None:
        """Admin marks any class; a teacher marks a class they teach a subject in.
        If a specific class-subject is given it must belong to this class."""
        if class_subject_id is not None:
            cs = self.db.scalar(
                select(ClassSubject).where(
                    ClassSubject.id == class_subject_id, ClassSubject.org_id == m.org_id))
            if cs is None:
                raise NotFoundError("Class-subject")
            if cs.class_id != class_id:
                raise ValidationError("That subject is not taught in this class.")
        if m.is_coordinator_up:
            return
        teaches = self.db.scalar(
            select(ClassSubject.id).where(
                ClassSubject.org_id == m.org_id, ClassSubject.class_id == class_id,
                ClassSubject.teacher_member_id == m.membership.id).limit(1))
        if teaches is None:
            raise ForbiddenError("You don't teach this class.", code="not_your_class")

    def _roster(self, org_id: uuid.UUID, class_id: uuid.UUID) -> list[Student]:
        return list(self.db.scalars(
            select(Student).where(
                Student.org_id == org_id, Student.class_id == class_id,
                Student.status == "active").order_by(Student.full_name)))

    # ── roster for the capture sheet ─────────────────────────────────────────
    def roster(self, m: CurrentMember, class_id: uuid.UUID, period_no: int,
               on_date: date | None = None) -> AttendanceRosterOut:
        klass = self._class(m.org_id, class_id)
        self._can_mark(m, class_id, None)
        d = on_date or self._today(m)
        roster = self._roster(m.org_id, class_id)
        mark = self.db.scalar(
            select(AttendanceMark).where(
                AttendanceMark.org_id == m.org_id, AttendanceMark.class_id == class_id,
                AttendanceMark.date == d, AttendanceMark.period_no == period_no)
            .options(selectinload(AttendanceMark.exceptions)))
        exc = {e.student_id: e for e in mark.exceptions} if mark else {}
        rows = [
            AttendanceRosterRow(
                student_id=s.id, full_name=s.full_name, roll_no=s.roll_no,
                status=exc[s.id].status if s.id in exc else None,
                late_minutes=exc[s.id].late_minutes if s.id in exc else None)
            for s in roster
        ]
        absent = sum(1 for r in rows if r.status == "absent")
        late = sum(1 for r in rows if r.status == "late")
        return AttendanceRosterOut(
            class_id=class_id, class_label=_label(klass), period_no=period_no, date=d,
            marked=mark is not None, roster=rows,
            present_count=len(rows) - absent, absent_count=absent, late_count=late)

    # ── mark (the one-tap capture) ───────────────────────────────────────────
    def mark(self, m: CurrentMember, body: AttendanceMarkIn) -> AttendanceMarkOut:
        klass = self._class(m.org_id, body.class_id)
        self._can_mark(m, body.class_id, body.class_subject_id)
        d = body.date or self._today(m)
        roster_ids = {s.id for s in self._roster(m.org_id, body.class_id)}

        mark = self.db.scalar(
            select(AttendanceMark).where(
                AttendanceMark.org_id == m.org_id, AttendanceMark.class_id == body.class_id,
                AttendanceMark.date == d, AttendanceMark.period_no == body.period_no)
            .options(selectinload(AttendanceMark.exceptions)))
        # Is this the class's first marked period of the day? (Decide before insert.)
        others = self.db.scalar(
            select(func.count(AttendanceMark.id)).where(
                AttendanceMark.org_id == m.org_id, AttendanceMark.class_id == body.class_id,
                AttendanceMark.date == d,
                AttendanceMark.period_no != body.period_no))
        is_new = mark is None
        first_of_day = is_new and (others or 0) == 0

        if mark is None:
            mark = AttendanceMark(
                org_id=m.org_id, class_id=body.class_id, date=d, period_no=body.period_no,
                class_subject_id=body.class_subject_id, marked_by_member_id=m.membership.id,
                marked_at=datetime.now(UTC))
            self.db.add(mark)
            self.db.flush()
        else:
            mark.class_subject_id = body.class_subject_id or mark.class_subject_id
            mark.marked_by_member_id = m.membership.id
            mark.marked_at = datetime.now(UTC)
            # Full-replace the exception set (idempotent re-capture).
            for e in list(mark.exceptions):
                self.db.delete(e)
            self.db.flush()

        absent_ids: list[uuid.UUID] = []
        for e in body.exceptions:
            if e.student_id not in roster_ids:
                continue  # ignore students not on this class's roster
            self.db.add(AttendanceException(
                org_id=m.org_id, mark_id=mark.id, student_id=e.student_id,
                status=e.status, late_minutes=e.late_minutes if e.status == "late" else None))
            if e.status == "absent":
                absent_ids.append(e.student_id)
        self.db.flush()

        alerted = 0
        if first_of_day and mark.alerted_at is None:
            alerted = self._alert_absences(m, klass, absent_ids, d)
            mark.alerted_at = datetime.now(UTC)
            self.db.flush()

        roster_count = len(roster_ids)
        absent_count = len(absent_ids)
        late_count = sum(1 for e in body.exceptions
                         if e.status == "late" and e.student_id in roster_ids)
        return AttendanceMarkOut(
            mark_id=mark.id, class_id=body.class_id, period_no=body.period_no, date=d,
            roster_count=roster_count, present_count=roster_count - absent_count,
            absent_count=absent_count, late_count=late_count, alerted_count=alerted)

    def _alert_absences(self, m: CurrentMember, klass: SchoolClass,
                        absent_ids: list[uuid.UUID], d: date) -> int:
        """Notify each absent student's guardians (§7). Plain text only (P4)."""
        if not absent_ids:
            return 0
        sent = 0
        rows = self.db.execute(
            select(Student.full_name, Guardian.phone, Guardian.notify_opt_out)
            .join(Guardian, Guardian.student_id == Student.id)
            .where(Student.org_id == m.org_id, Student.id.in_(absent_ids))
        ).all()
        # Group guardians by student so each family gets one message.
        by_student: dict[str, list[tuple[str | None, bool]]] = {}
        for full_name, phone, opt_out in rows:
            by_student.setdefault(full_name, []).append((phone, opt_out))
        for full_name, recipients in by_student.items():
            message = f"{full_name} was marked absent at {m.org.name} today ({d.isoformat()})."
            sent += notify_guardians(recipients, message)
        return sent

    # ── My Day integration: per-period state for a set of classes ────────────
    def roster_sizes(
        self, org_id: uuid.UUID, class_ids: list[uuid.UUID],
    ) -> dict[uuid.UUID, int]:
        """class_id → active-roster size (shown on the card even before marking)."""
        if not class_ids:
            return {}
        return dict(self.db.execute(
            select(Student.class_id, func.count(Student.id))
            .where(Student.org_id == org_id, Student.class_id.in_(class_ids),
                   Student.status == "active")
            .group_by(Student.class_id)
        ).all())

    def period_states(
        self, org_id: uuid.UUID, class_ids: list[uuid.UUID], on_date: date,
    ) -> dict[tuple[uuid.UUID, int], dict]:
        """(class_id, period_no) → {marked, roster_count, present_count, absent_count,
        late_count} for the MARKED periods only. Roster size for unmarked periods
        comes from roster_sizes()."""
        if not class_ids:
            return {}
        roster_counts = self.roster_sizes(org_id, class_ids)
        marks = list(self.db.scalars(
            select(AttendanceMark).where(
                AttendanceMark.org_id == org_id, AttendanceMark.class_id.in_(class_ids),
                AttendanceMark.date == on_date)
            .options(selectinload(AttendanceMark.exceptions))))
        out: dict[tuple[uuid.UUID, int], dict] = {}
        for mk in marks:
            absent = sum(1 for e in mk.exceptions if e.status == "absent")
            late = sum(1 for e in mk.exceptions if e.status == "late")
            roster_count = roster_counts.get(mk.class_id, 0)
            out[(mk.class_id, mk.period_no)] = {
                "marked": True, "roster_count": roster_count,
                "present_count": roster_count - absent,
                "absent_count": absent, "late_count": late}
        return out
