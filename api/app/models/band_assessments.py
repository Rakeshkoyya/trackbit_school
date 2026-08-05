"""The support programme's own assessments (founder 2026-08-05).

The owner of a handful of Band C children could give them work — per-student
homework, reused deliberately (`SupportAssignments`) — and could write a weekly
check-in. What she could not do was **set a check and record how each child did
on it**, which is the one thing that tells her whether the last three weeks
moved anybody.

Three tables, and the shape of each is decided by an existing precedent:

    band_assessments            the thing she set — name, what to do, and the
                                metric she will judge it on
    band_assessment_students    the explicit roster, when it is not everyone
                                (HS-1's `session_students`: `covers_all` means
                                the roster is COMPUTED, so a child assigned to
                                her next week appears with zero edits)
    band_assessment_results     one row per child evaluated — full-replace on
                                save, exactly like `homework_results` and
                                `attendance_exceptions`

**Why not `assessment_cycles`.** That table is the school's academic record: it
carries `core/exams.py`'s scale, verify-and-lock, question marks, and it moves a
child's band under `D-76`. A support owner's 1-to-5 reading rating must never
reach any of that — `ScaleTally` refuses to pool scales precisely so nobody can
add a slip test to a term paper by accident, and this would have been that
mistake with a rating instead of a mark. The vocabulary and the arithmetic live
in `core/band_assessment.py`; import them, never re-decide them.

**Results are capture, not a decision** — so they are a full replace and not an
append log (law 3 governs decisions: a band, an approval, a fee conversation).
A teacher who mistypes 7 for 17 corrects it in place, the same way she corrects a
mis-tapped absence. What a child was *judged* to be — his band — is still
append-only, and this never writes one.

Staff-only, like everything else in the programme (P4). Nothing here has a path
to a parent surface: `services/parent_portal.py` is an allowlist built field by
field, so these tables stay out of it by construction.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import CreatedAtMixin, UUIDPKMixin

_MARKS = Numeric(6, 2)


def _org_fk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )


class BandAssessment(Base, UUIDPKMixin, CreatedAtMixin):
    """One check she set for her support children in one class."""

    __tablename__ = "band_assessments"

    org_id: Mapped[uuid.UUID] = _org_fk()
    class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("school_classes.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # The monitored subject this belongs to. Nullable because a support owner is
    # sometimes working on something that crosses subjects ("sitting still for
    # twenty minutes"), and refusing to record that would push it into a
    # notebook. Where it is set, the assessment files under that subject's
    # programme.
    subject_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True,
    )
    term_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("terms.id", ondelete="SET NULL"), nullable=True,
    )

    name: Mapped[str] = mapped_column(Text, nullable=False)
    # "What they need to do" — the instruction the child is given, kept apart
    # from the teacher's own note about why. Two fields because they are read by
    # two different people at two different moments.
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    metric: Mapped[str] = mapped_column(Text, nullable=False, server_default="marks")
    # Only meaningful for `marks` / `rating` respectively. Kept nullable rather
    # than defaulted so "she never said" is distinguishable from "out of 1".
    max_marks: Mapped[float | None] = mapped_column(_MARKS, nullable=True)
    rating_max: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # HS-1's rule: True = the roster is COMPUTED (every support child of this
    # member in this class), so a child assigned next week is on it without
    # anyone remembering to edit. False = the explicit rows below.
    covers_all: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true")

    given_on: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # SET NULL so the record outlives the account (the `fee_notes` rule).
    created_by_member_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memberships.id", ondelete="SET NULL"), nullable=True,
    )

    __table_args__ = (
        CheckConstraint("metric IN ('marks', 'rating', 'other')",
                        name="ck_band_assessments_metric"),
    )


class BandAssessmentStudent(Base, UUIDPKMixin, CreatedAtMixin):
    """The explicit roster — only when `covers_all` is False.

    "All my students" is not stored as forty rows, because storing it that way
    is what makes a roster go stale (HS-1, `session_classes`)."""

    __tablename__ = "band_assessment_students"

    org_id: Mapped[uuid.UUID] = _org_fk()
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("band_assessments.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    __table_args__ = (
        UniqueConstraint("assessment_id", "student_id",
                         name="uq_band_assessment_students"),
    )


class BandAssessmentResult(Base, UUIDPKMixin, CreatedAtMixin):
    """How one child did. **Its absence means not evaluated**, never zero.

    One column per metric rather than a polymorphic `value`, so a rating can
    never be summed with a mark by a query that forgot to check the metric —
    the same reason `core/band_assessment.py` has no blended average."""

    __tablename__ = "band_assessment_results"

    org_id: Mapped[uuid.UUID] = _org_fk()
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("band_assessments.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    marks: Mapped[float | None] = mapped_column(_MARKS, nullable=True)
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # `other`: her own word for how it went.
    verdict: Mapped[str | None] = mapped_column(Text, nullable=True)
    # A remark that belongs to the number, not to the child. The child's own log
    # is `student_notes` — durable, append-only, and readable a year later
    # beside everything else anyone noticed about him.
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    recorded_by_member_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memberships.id", ondelete="SET NULL"), nullable=True,
    )
    recorded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("assessment_id", "student_id",
                         name="uq_band_assessment_results"),
    )
