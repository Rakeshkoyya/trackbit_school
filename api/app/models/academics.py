"""Academic master data (SPRD §4.2) — the shared spine under academics AND fees.

Years/terms/classes/subjects are referenced by students, sessions, assessments
and the ported fee tables alike; unifying them is the reason the two products
merge into one app (SPRD §2.2). All tables carry org_id + RLS.
"""

import uuid
from datetime import date

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import CreatedAtMixin, UUIDPKMixin


def _org_fk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )


class AcademicYear(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "academic_years"

    org_id: Mapped[uuid.UUID] = _org_fk()
    label: Mapped[str] = mapped_column(Text, nullable=False)  # "2026-27"
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    # Exactly one active year per org is enforced in the service layer, not the DB
    # (a partial unique index would fight the archive-on-replace flow).
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    # Working weekdays as Python weekday ints (Mon=0 … Sun=6). Default Mon–Sat —
    # the Indian-school norm. Drives the effective-teaching-days engine (M1).
    working_weekdays: Mapped[list[int]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[0, 1, 2, 3, 4, 5]'::jsonb")
    )
    # School timings (V2-M1 wizard step 3 / M3 timetable). periods_per_day bounds
    # the timetable grid; period_times is a JSON list of {start,end,kind} incl.
    # breaks (e.g. {"start":"09:00","end":"09:40","kind":"period"}). Empty until set.
    periods_per_day: Mapped[int] = mapped_column(Integer, nullable=False, server_default="8")
    period_times: Mapped[list[dict]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )

    terms: Mapped[list["Term"]] = relationship(
        "Term", back_populates="academic_year", cascade="all, delete-orphan",
        order_by="Term.start_date",
    )

    __table_args__ = (UniqueConstraint("org_id", "label", name="uq_academic_years_org_id"),)


class Term(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "terms"

    org_id: Mapped[uuid.UUID] = _org_fk()
    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic_years.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)  # "Term 1"
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)

    academic_year: Mapped["AcademicYear"] = relationship("AcademicYear", back_populates="terms")


class Subject(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "subjects"

    org_id: Mapped[uuid.UUID] = _org_fk()
    name: Mapped[str] = mapped_column(Text, nullable=False)  # "Mathematics"

    __table_args__ = (UniqueConstraint("org_id", "name", name="uq_subjects_org_id"),)


class SchoolClass(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "school_classes"

    org_id: Mapped[uuid.UUID] = _org_fk()
    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic_years.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)  # "6"
    section: Mapped[str | None] = mapped_column(Text, nullable=True)  # "B"
    # The class teacher (homeroom). SET NULL if that membership is later removed.
    class_teacher_member_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memberships.id", ondelete="SET NULL"), nullable=True
    )

    class_subjects: Mapped[list["ClassSubject"]] = relationship(
        "ClassSubject", back_populates="school_class", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint(
            "org_id", "academic_year_id", "name", "section",
            name="uq_school_classes_org_id",
        ),
    )


class ClassSubject(Base, UUIDPKMixin, CreatedAtMixin):
    """A subject taught in a class by a teacher, with its weekly period budget.

    periods_per_week is *entered*, never generated — TrackBit has no timetable
    solver (SPRD §11 fence); it only captures the allocation as data.
    """

    __tablename__ = "class_subjects"

    org_id: Mapped[uuid.UUID] = _org_fk()
    class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("school_classes.id", ondelete="CASCADE"), nullable=False
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False
    )
    teacher_member_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memberships.id", ondelete="SET NULL"), nullable=True
    )
    periods_per_week: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    school_class: Mapped["SchoolClass"] = relationship(
        "SchoolClass", back_populates="class_subjects"
    )
    subject: Mapped["Subject"] = relationship("Subject")

    __table_args__ = (
        UniqueConstraint("class_id", "subject_id", name="uq_class_subjects_class_id"),
    )


class CalendarEvent(Base, UUIDPKMixin, CreatedAtMixin):
    """School-calendar entry (SPRD §4.3). affects_teaching marks days the
    effective-days engine removes from the teaching total (holidays, exam blocks,
    events, celebrations)."""

    __tablename__ = "calendar_events"

    org_id: Mapped[uuid.UUID] = _org_fk()
    academic_year_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("academic_years.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    affects_teaching: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    # Which periods this event eats, e.g. [1, 2, 3] for a morning exam. NULL means
    # the whole day (the common case). A day with blocks_periods set is a PARTIAL
    # day: it still teaches, just fewer periods — the effective-days engine prorates
    # it rather than removing it (V2-P7).
    blocks_periods: Mapped[list[int] | None] = mapped_column(JSONB, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "type IN ('holiday', 'exam_block', 'event', 'celebration')", name="type_valid"
        ),
    )
