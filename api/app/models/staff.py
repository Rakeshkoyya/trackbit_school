"""Staff presence, time and leave (SF-1, founder decision 2026-07-29).

Three things the school could not record before this module: whether a staff
member turned up, what a teacher does with the periods they are not teaching,
and who is allowed to be away.

**Staff attendance is admin-marked and exception-shaped** (P1v2), the same
capture the classroom already uses for students: `staff_attendance_days` says
"attendance was taken for this date", and `staff_absences` carries a row ONLY
for the people who were away. Present is derived — roster minus absences — so
there are no per-member present rows to write, and "everyone came in" is an
empty exception set.

SF-1 shipped this present/absent only. **`D-04` (V1-4) reversed that**: the row
now carries a `status` of absent · half_day · late, and a half-day carries the
AM/PM `portion`, because `D-78`'s month summary is *days worked out of working
days* and a half day is half a day. The widening stayed inside the existing row
(`S-18`) — a second table would fork the truth about one person's one day.

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
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
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
    """An exception row: this member did not have a normal full day.

    Still one row per person per day and still a full replace — `status` widens
    what the row can say (V1-4, `D-04`/`S-18`) rather than adding a table:

      * ``absent``   — not in at all. Worth 0 days present.
      * ``half_day`` — in for one half; ``portion`` says WHICH half, because the
        cover board's whole job is knowing which periods need covering and "0.5
        days" cannot answer that (`S-31`). Worth 0.5.
      * ``late``     — in, but not on time. **Worth a full day present** (`D-04`
        counts days present; lateness is a flag, not a deduction — `S-19`), so a
        late row exists to be seen and counted, never to reduce anything.

    Present with nothing to say is still no row at all.
    """

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
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="absent")
    portion: Mapped[str | None] = mapped_column(Text, nullable=True)  # am | pm
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    day: Mapped["StaffAttendanceDay"] = relationship(back_populates="absences")

    __table_args__ = (
        UniqueConstraint("day_id", "member_id", name="uq_staff_absences_day_member"),
        CheckConstraint("source IN ('manual', 'leave')", name="staff_absence_source_valid"),
        CheckConstraint("status IN ('absent', 'half_day', 'late')",
                        name="staff_absence_status_valid"),
        CheckConstraint("portion IS NULL OR portion IN ('am', 'pm')",
                        name="staff_absence_portion_valid"),
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
    # Numeric since V1-4: a half-day is 0.5 here rather than a second column the
    # balance arithmetic has to remember to subtract (D-04).
    days: Mapped[float] = mapped_column(
        Numeric(4, 1, asdecimal=False), nullable=False, server_default="1")
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="pending")
    # D-04 — half-day leave. `portion` says which half, so the cover board knows
    # which periods to fill (S-31). Constrained to a single date by the DB.
    is_half_day: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false"))
    portion: Mapped[str | None] = mapped_column(Text, nullable=True)  # am | pm

    events: Mapped[list["LeaveRequestEvent"]] = relationship(
        back_populates="request", cascade="all, delete-orphan",
        order_by="LeaveRequestEvent.created_at",
    )

    __table_args__ = (
        CheckConstraint("end_date >= start_date", name="leave_dates_valid"),
        CheckConstraint("status IN ('pending', 'approved', 'rejected', 'cancelled')",
                        name="leave_status_valid"),
        CheckConstraint("portion IS NULL OR portion IN ('am', 'pm')",
                        name="leave_portion_valid"),
        CheckConstraint("is_half_day IS FALSE OR start_date = end_date",
                        name="leave_half_day_single"),
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
