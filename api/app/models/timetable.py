"""Timetable slots (V2-M3, SPRD2 §4, §5.3).

A slot is one class-period cell: (class_id, weekday, period_no) → class_subject.
Editing mid-year is append-only (Law 3): the old row is *closed* (effective_to set
to the edit date) and a new row opened, so historical joins — "what was student S
doing in this period back in August" — stay truthful. The current grid is the set
of rows with effective_to IS NULL (or > the date of interest).

Period *timing* (periods_per_day, period_times) lives on academic_years, not here.
"""

import uuid
from datetime import date

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import CreatedAtMixin, UUIDPKMixin


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
    class_subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("class_subjects.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # Effective-dating: [effective_from, effective_to). NULL effective_to = current.
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)

    __table_args__ = (
        CheckConstraint("weekday >= 0 AND weekday <= 6", name="weekday_valid"),
        CheckConstraint("period_no >= 1", name="period_no_valid"),
        # Fast lookup of a class's current grid.
        Index("ix_timetable_slots_class_current", "class_id", "effective_to"),
    )
