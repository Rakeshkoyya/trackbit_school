"""The school day: its shape (`bell_schedules`) and its content (`timetable_slots`).

**The bell schedule says when, the slot says what** (TT-2).

A slot is one class-period cell: `(class_id, weekday, period_no)` → either a
class-subject or a *block* (a `Session` — homework class, sports, assembly…).
Editing mid-year is append-only (Law 3): the old row is *closed* (effective_to
set to the edit date) and a new row opened, so historical joins — "what was
student S doing in this period back in August" — stay truthful. The current grid
is the set of rows with effective_to IS NULL (or > the date of interest).

A bell schedule is effective-dated for the same reason and by the same rule
(`D-115`). Before TT-2 the timings were a single JSONB on `academic_years`, so a
school that restructured its day after the Term 1 exams silently re-rendered
September's timesheets and day-books with October's clock. Timings are history
too; they get a table.
"""

import uuid
from datetime import date

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Integer, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import CreatedAtMixin, UUIDPKMixin


class BellSchedule(Base, UUIDPKMixin, CreatedAtMixin):
    """The shape of the school day over a date range.

    `entries` is a wall-clock-ordered JSON list of `{start, end, kind, label}`
    that INCLUDES breaks. The mapping to the period numbers everything else uses
    lives in `services/school_clock.py` and nowhere else:

        period_no = the 1-based index among entries whose kind == 'period'

    so inserting a lunch break shifts no period number, and appending a 15:30
    homework block simply makes it period 9. That is what lets TT-2 extend the
    day past 2pm without migrating a single `class_periods` row.
    """

    __tablename__ = "bell_schedules"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic_years.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # Teachable periods only — the count of kind == 'period' entries. Stored
    # rather than derived so a school that never set its timings (entries == [])
    # still renders a numbered, fillable grid.
    periods_per_day: Mapped[int] = mapped_column(Integer, nullable=False, server_default="8")
    entries: Mapped[list[dict]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    # Why the day changed — "after Term 1 exams". Shown in the history list.
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Effective-dating: [effective_from, effective_to). NULL effective_to = current.
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)

    __table_args__ = (
        CheckConstraint("periods_per_day >= 0 AND periods_per_day <= 16",
                        name="bell_periods_per_day_valid"),
        Index("ix_bell_schedules_year_current", "academic_year_id", "effective_to"),
    )


class TimetableSlot(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "timetable_slots"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("school_classes.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # Python weekday int (Mon=0 … Sun=6).
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)
    # 1-based period index within the day.
    period_no: Mapped[int] = mapped_column(Integer, nullable=False)
    # 'subject' | 'block' — see core/day_shape.SLOT_TYPES. A block's *flavour*
    # (homework / sports / assembly …) is `sessions.kind`, deliberately not
    # copied here: two stores for one fact diverge on the first edit.
    slot_type: Mapped[str] = mapped_column(Text, nullable=False, server_default="subject")
    # Set when slot_type == 'subject'. Nullable since TT-2.
    class_subject_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("class_subjects.id", ondelete="CASCADE"),
        nullable=True, index=True,
    )
    # Set when slot_type == 'block'. SET NULL rather than CASCADE so deleting a
    # session cannot silently punch holes in historical grid rows; the service
    # closes the slots first.
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    # Effective-dating: [effective_from, effective_to). NULL effective_to = current.
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)

    __table_args__ = (
        CheckConstraint("weekday >= 0 AND weekday <= 6", name="weekday_valid"),
        CheckConstraint("period_no >= 1", name="period_no_valid"),
        # A cell holds exactly one thing. Without this, a slot could be written
        # with both ids set and the two renderings of it would disagree.
        CheckConstraint(
            "(slot_type = 'subject' AND class_subject_id IS NOT NULL AND session_id IS NULL)"
            " OR (slot_type = 'block' AND session_id IS NOT NULL AND class_subject_id IS NULL)",
            name="slot_payload_valid",
        ),
        # Fast lookup of a class's current grid.
        Index("ix_timetable_slots_class_current", "class_id", "effective_to"),
    )
