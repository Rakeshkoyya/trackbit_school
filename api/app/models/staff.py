"""Staff presence, time and leave (SF-1, founder decision 2026-07-29).

Three things the school could not record before this module: whether a staff
member turned up, what a teacher does with the periods they are not teaching,
and who is allowed to be away.

**Staff attendance is admin-marked and exception-shaped** (P1v2), the same
capture the classroom already uses for students: `staff_attendance_days` says
"attendance was taken for this date", and `staff_absences` carries a row ONLY
for the people who were away. Present is derived — roster minus absences — so
there are no per-member present rows to write, and "everyone came in" is an
empty exception set. Founder call: **present/absent only, no late tier** for
staff; a teacher who arrives late is present, and the timetable already records
which period they actually took.

Re-marking is a full replace of the absence set, exactly like
`AttendanceService.mark`, so the admin can reopen the day and correct it without
any undo machinery. The day row remembers who last touched it.

**Timesheet** (`timesheet_entries`) is the teacher's own record of a *non-teaching*
period. Teaching periods are never stored here — they already exist in
`timetable_slots`, and duplicating them would create two sources of truth that
drift the moment the grid changes. One row per (member, date, period_no), so a
period is either free, teaching, or exactly one piece of work. This is what makes
"who is free right now" answerable, and it is real capture rather than an
inference from the task board.

**Leave** follows the append-only law (3) in the shape `plan_approvals` and
`demo_request_notes` established: `leave_request_events` is the history — applied,
approved, rejected, cancelled, each with its actor — and `leave_requests.status`
is a derived cache of the newest event. A decision is never overwritten.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import CreatedAtMixin, UUIDPKMixin


def _org_fk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )


class StaffAttendanceDay(Base, UUIDPKMixin, CreatedAtMixin):
    """One row per org × date — "staff attendance was taken on this day".

    Its existence is the difference between "nobody was absent" and "nobody
    marked it", which is the same distinction student attendance draws with
    `class_periods.attendance_marked_at`. Without it an unmarked morning would
    read as a full house.
    """

    __tablename__ = "staff_attendance_days"

    org_id: Mapped[uuid.UUID] = _org_fk()
    date: Mapped[date] = mapped_column(Date, nullable=False)
    marked_by_member_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memberships.id", ondelete="SET NULL"), nullable=True
    )
    marked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    absences: Mapped[list["StaffAbsence"]] = relationship(
        back_populates="day", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("org_id", "date", name="uq_staff_attendance_days_org_date"),
    )


class StaffAbsence(Base, UUIDPKMixin, CreatedAtMixin):
    """An exception row: this member was NOT in on this day. No present rows."""

    __tablename__ = "staff_absences"

    org_id: Mapped[uuid.UUID] = _org_fk()
    day_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff_attendance_days.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memberships.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # 'manual' = the admin unchecked them · 'leave' = an approved leave request
    # covered this date, so the roster pre-unchecked them.
    source: Mapped[str] = mapped_column(Text, nullable=False, server_default="manual")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    day: Mapped["StaffAttendanceDay"] = relationship(back_populates="absences")

    __table_args__ = (
        UniqueConstraint("day_id", "member_id", name="uq_staff_absences_day_member"),
        CheckConstraint("source IN ('manual', 'leave')", name="staff_absence_source_valid"),
    )


class TimesheetEntry(Base, UUIDPKMixin, CreatedAtMixin):
    """What a teacher did with a period they were not scheduled to teach.

    Only non-teaching periods land here. A period the timetable already fills is
    rendered from `timetable_slots` and cannot be overwritten — one source of
    truth per period.
    """

    __tablename__ = "timesheet_entries"

    org_id: Mapped[uuid.UUID] = _org_fk()
    member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memberships.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    # 1-based index among period_times entries with kind == 'period'.
    period_no: Mapped[int] = mapped_column(Integer, nullable=False)
    # See core/work_types.py. Unknown values are not rejected at the DB level —
    # a school renaming its work never loses data; the UI folds them into "Other".
    work_type: Mapped[str] = mapped_column(Text, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        UniqueConstraint("org_id", "member_id", "date", "period_no",
                         name="uq_timesheet_entries_member_date_period"),
        Index("ix_timesheet_entries_org_date", "org_id", "date"),
        CheckConstraint("period_no >= 1", name="timesheet_period_no_valid"),
    )


class LeaveRequest(Base, UUIDPKMixin, CreatedAtMixin):
    """A teacher's leave application. `status` is a DERIVED CACHE of the newest
    `leave_request_events` row — never the record of the decision itself (law 3).
    """

    __tablename__ = "leave_requests"

    org_id: Mapped[uuid.UUID] = _org_fk()
    member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memberships.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    # Working days in the range, computed at apply time from the year's
    # working_weekdays and calendar holidays — a Sunday inside a leave span is
    # not a leave day, and the balance would be wrong if we stored raw span.
    days: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="pending")

    events: Mapped[list["LeaveRequestEvent"]] = relationship(
        back_populates="request", cascade="all, delete-orphan",
        order_by="LeaveRequestEvent.created_at",
    )

    __table_args__ = (
        CheckConstraint("end_date >= start_date", name="leave_dates_valid"),
        CheckConstraint("status IN ('pending', 'approved', 'rejected', 'cancelled')",
                        name="leave_status_valid"),
        Index("ix_leave_requests_org_status", "org_id", "status"),
    )


class LeaveRequestEvent(Base):
    """Append-only history on a leave request. Nothing here is ever updated.

    `actor_member_id` is SET NULL so the history outlives a departing member —
    the same choice `demo_request_notes.author_user_id` makes.
    """

    __tablename__ = "leave_request_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    org_id: Mapped[uuid.UUID] = _org_fk()
    request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leave_requests.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    action: Mapped[str] = mapped_column(Text, nullable=False)
    actor_member_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memberships.id", ondelete="SET NULL"), nullable=True
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    request: Mapped["LeaveRequest"] = relationship(back_populates="events")

    __table_args__ = (
        CheckConstraint(
            "action IN ('applied', 'approved', 'rejected', 'cancelled')",
            name="leave_event_action_valid",
        ),
    )
