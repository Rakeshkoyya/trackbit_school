"""Per-period attendance (V2-M4, SPRD2 §5.4) — capture-by-exception.

"All present ✓" stamps `attendance_marked_at` on the class period; the teacher taps
only deviations, which become `attendance_exceptions` (absent | late). Present is
derived: roster minus absentees (late students are present-but-flagged).

The period row itself is the anchor (see models/periods.py). Marking opens it if
the teacher never tapped "Start attendance" — so the one-tap "All present" path
straight off a My Day card still works without a separate open call.

The day's FIRST attendance-marked period for a class fires guardian absence alerts
(§7) once — `alerted_at` on that period makes it idempotent across re-marks/edits.
Alerts carry plain "absent today" text only; never band/tier info (P4).
"""

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.context import CurrentMember
from app.core.exceptions import NotFoundError
from app.models import (
    AttendanceException,
    ClassPeriod,
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
from app.services.periods import (
    assert_can_take_class,
    find_period,
    get_or_create_period,
    today_for,
)


def _label(klass: SchoolClass) -> str:
    return klass.name + (f"-{klass.section}" if klass.section else "")


class AttendanceService:
    def __init__(self, db: Session):
        self.db = db

    def _today(self, m: CurrentMember) -> date:
        return today_for(m)

    def _class(self, org_id: uuid.UUID, class_id: uuid.UUID) -> SchoolClass:
        klass = self.db.scalar(
            select(SchoolClass).where(SchoolClass.id == class_id, SchoolClass.org_id == org_id))
        if klass is None:
            raise NotFoundError("Class")
        return klass

    def _roster(self, org_id: uuid.UUID, class_id: uuid.UUID) -> list[Student]:
        return list(self.db.scalars(
            select(Student).where(
                Student.org_id == org_id, Student.class_id == class_id,
                Student.status == "active").order_by(Student.full_name)))

    # ── roster for the capture sheet ─────────────────────────────────────────
    def roster(self, m: CurrentMember, class_id: uuid.UUID, period_no: int,
               on_date: date | None = None) -> AttendanceRosterOut:
        klass = self._class(m.org_id, class_id)
        assert_can_take_class(self.db, m, class_id, None)
        d = on_date or self._today(m)
        roster = self._roster(m.org_id, class_id)
        period = self.db.scalar(
            select(ClassPeriod).where(
                ClassPeriod.org_id == m.org_id, ClassPeriod.class_id == class_id,
                ClassPeriod.date == d, ClassPeriod.period_no == period_no)
            .options(selectinload(ClassPeriod.exceptions)))
        exc = {e.student_id: e for e in period.exceptions} if period else {}
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
            period_id=period.id if period else None,
            marked=period is not None and period.attendance_marked_at is not None,
            roster=rows,
            present_count=len(rows) - absent, absent_count=absent, late_count=late)

    # ── mark (the one-tap capture) ───────────────────────────────────────────
    def mark(self, m: CurrentMember, body: AttendanceMarkIn) -> AttendanceMarkOut:
        klass = self._class(m.org_id, body.class_id)
        assert_can_take_class(self.db, m, body.class_id, body.class_subject_id)
        d = body.date or self._today(m)
        roster_ids = {s.id for s in self._roster(m.org_id, body.class_id)}

        existing = find_period(self.db, m.org_id, body.class_id, d, body.period_no)
        # First *attendance-marked* period of the day for this class? Decide before
        # we stamp this one. An opened-but-unmarked period must not count.
        others_marked = self.db.scalar(
            select(func.count(ClassPeriod.id)).where(
                ClassPeriod.org_id == m.org_id, ClassPeriod.class_id == body.class_id,
                ClassPeriod.date == d, ClassPeriod.period_no != body.period_no,
                ClassPeriod.attendance_marked_at.is_not(None)))
        already_marked = existing is not None and existing.attendance_marked_at is not None
        first_of_day = not already_marked and (others_marked or 0) == 0

        period = get_or_create_period(
            self.db, m, body.class_id, d, body.period_no, body.class_subject_id)
        if body.class_subject_id is not None:
            period.class_subject_id = body.class_subject_id
        period.marked_by_member_id = m.membership.id
        period.attendance_marked_at = datetime.now(UTC)
        if period.teacher_member_id is None:
            period.teacher_member_id = m.membership.id
        # Full-replace the exception set (idempotent re-capture).
        self.db.execute(
            AttendanceException.__table__.delete().where(
                AttendanceException.period_id == period.id))
        self.db.flush()

        absent_ids: list[uuid.UUID] = []
        for e in body.exceptions:
            if e.student_id not in roster_ids:
                continue  # ignore students not on this class's roster
            self.db.add(AttendanceException(
                org_id=m.org_id, period_id=period.id, student_id=e.student_id,
                status=e.status, late_minutes=e.late_minutes if e.status == "late" else None))
            if e.status == "absent":
                absent_ids.append(e.student_id)
        self.db.flush()

        alerted = 0
        if first_of_day and period.alerted_at is None:
            alerted = self._alert_absences(m, klass, absent_ids, d)
            period.alerted_at = datetime.now(UTC)
            self.db.flush()

        roster_count = len(roster_ids)
        absent_count = len(absent_ids)
        late_count = sum(1 for e in body.exceptions
                         if e.status == "late" and e.student_id in roster_ids)
        return AttendanceMarkOut(
            period_id=period.id, mark_id=period.id, class_id=body.class_id,
            period_no=body.period_no, date=d,
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
        """(class_id, period_no) → card state for every *opened* period. `marked` is
        false for a period that was opened but whose attendance was never submitted.
        Roster size for un-opened periods comes from roster_sizes()."""
        if not class_ids:
            return {}
        roster_counts = self.roster_sizes(org_id, class_ids)
        periods = list(self.db.scalars(
            select(ClassPeriod).where(
                ClassPeriod.org_id == org_id, ClassPeriod.class_id.in_(class_ids),
                ClassPeriod.date == on_date)
            .options(selectinload(ClassPeriod.exceptions))))
        out: dict[tuple[uuid.UUID, int], dict] = {}
        for p in periods:
            marked = p.attendance_marked_at is not None
            absent = sum(1 for e in p.exceptions if e.status == "absent")
            late = sum(1 for e in p.exceptions if e.status == "late")
            roster_count = roster_counts.get(p.class_id, 0)
            out[(p.class_id, p.period_no)] = {
                "period_id": p.id, "status": p.status,
                "closed": p.closed_at is not None,
                "marked": marked, "roster_count": roster_count,
                "present_count": roster_count - absent if marked else None,
                "absent_count": absent if marked else None,
                "late_count": late if marked else None}
        return out
