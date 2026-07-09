"""Class-period lifecycle (V2-P6) — open, close, mark not-held.

Open-on-action: the row is created by the teacher's first real action on the card,
which the UI hides behind the "Start attendance" button. The timetable already
records that the period was *scheduled*, so a missing `class_periods` row means
"nothing was captured" with no ambiguity — and no write happens on the read path.

Card assembly (attendance + plan + homework) lives in ClassroomService, which is
the surface that owns My Day; this module is lifecycle only, so `attendance.py`
can import the guard and the get-or-create without a cycle.
"""

import uuid
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.models import ClassPeriod, ClassSubject, SchoolClass


def today_for(m: CurrentMember) -> date:
    return datetime.now(ZoneInfo(m.org.timezone)).date()


def assert_can_take_class(
    db: Session, m: CurrentMember, class_id: uuid.UUID, class_subject_id: uuid.UUID | None,
) -> None:
    """Admin takes any class; a teacher takes a class they teach a subject in.
    A given class-subject must belong to that class."""
    if class_subject_id is not None:
        cs = db.scalar(select(ClassSubject).where(
            ClassSubject.id == class_subject_id, ClassSubject.org_id == m.org_id))
        if cs is None:
            raise NotFoundError("Class-subject")
        if cs.class_id != class_id:
            raise ValidationError("That subject is not taught in this class.")
    if m.is_coordinator_up:
        return
    teaches = db.scalar(select(ClassSubject.id).where(
        ClassSubject.org_id == m.org_id, ClassSubject.class_id == class_id,
        ClassSubject.teacher_member_id == m.membership.id).limit(1))
    if teaches is None:
        raise ForbiddenError("You don't teach this class.", code="not_your_class")


def find_period(
    db: Session, org_id: uuid.UUID, class_id: uuid.UUID, d: date, period_no: int,
) -> ClassPeriod | None:
    return db.scalar(select(ClassPeriod).where(
        ClassPeriod.org_id == org_id, ClassPeriod.class_id == class_id,
        ClassPeriod.date == d, ClassPeriod.period_no == period_no))


def get_or_create_period(
    db: Session, m: CurrentMember, class_id: uuid.UUID, d: date, period_no: int,
    class_subject_id: uuid.UUID | None,
) -> ClassPeriod:
    """Idempotent open. `teacher_member_id` records who actually took this
    occurrence — a substitution is simply a period whose teacher differs from the
    class-subject's year-long assignment."""
    period = find_period(db, m.org_id, class_id, d, period_no)
    if period is None:
        period = ClassPeriod(
            org_id=m.org_id, class_id=class_id, date=d, period_no=period_no,
            class_subject_id=class_subject_id, teacher_member_id=m.membership.id,
            opened_at=datetime.now(UTC), status="held")
        db.add(period)
        db.flush()
    elif class_subject_id is not None and period.class_subject_id is None:
        period.class_subject_id = class_subject_id
        db.flush()
    return period


class PeriodService:
    def __init__(self, db: Session):
        self.db = db

    def _class(self, org_id: uuid.UUID, class_id: uuid.UUID) -> SchoolClass:
        klass = self.db.scalar(select(SchoolClass).where(
            SchoolClass.id == class_id, SchoolClass.org_id == org_id))
        if klass is None:
            raise NotFoundError("Class")
        return klass

    def _period(self, m: CurrentMember, period_id: uuid.UUID) -> ClassPeriod:
        period = self.db.scalar(select(ClassPeriod).where(
            ClassPeriod.id == period_id, ClassPeriod.org_id == m.org_id))
        if period is None:
            raise NotFoundError("Period")
        assert_can_take_class(self.db, m, period.class_id, None)
        return period

    def open(self, m: CurrentMember, class_id: uuid.UUID, period_no: int,
             class_subject_id: uuid.UUID | None, on_date: date | None = None) -> ClassPeriod:
        self._class(m.org_id, class_id)
        assert_can_take_class(self.db, m, class_id, class_subject_id)
        d = on_date or today_for(m)
        return get_or_create_period(self.db, m, class_id, d, period_no, class_subject_id)

    def close(self, m: CurrentMember, period_id: uuid.UUID) -> ClassPeriod:
        """Close-out is the teacher's "done with this period" signal. It does not
        require attendance — a not-held period closes too — so the 16:00 reminder
        job and the daily report can both read `closed_at` as ground truth."""
        period = self._period(m, period_id)
        if period.closed_at is None:
            period.closed_at = datetime.now(UTC)
            self.db.flush()
        return period

    def reopen(self, m: CurrentMember, period_id: uuid.UUID) -> ClassPeriod:
        period = self._period(m, period_id)
        period.closed_at = None
        self.db.flush()
        return period

    def not_held(self, m: CurrentMember, period_id: uuid.UUID, reason: str) -> ClassPeriod:
        """The class did not happen. Keeps the period row (so the day's coverage
        arithmetic still balances) and closes it out with a reason."""
        period = self._period(m, period_id)
        period.status = "not_held"
        period.not_held_reason = reason
        if period.closed_at is None:
            period.closed_at = datetime.now(UTC)
        self.db.flush()
        return period
