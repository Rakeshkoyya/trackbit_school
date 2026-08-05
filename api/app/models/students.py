"""Students, guardians, and fee categories (SPRD §4.2).

The single student master used by fees, academics, sessions, and assessments —
no second roster, no sync hell (SPRD §2.2). Guardians are records only: parents
have no login in v1 and receive outbound notifications only (SPRD §3.4).
"""

import uuid
from datetime import date

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
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


class StudentCategory(Base, UUIDPKMixin, CreatedAtMixin):
    """Fee category (ported from the fee system as data, not an enum). Per-org;
    seeded with "Day Scholar" / "Hosteller" and editable in Settings."""

    __tablename__ = "student_categories"

    org_id: Mapped[uuid.UUID] = _org_fk()
    name: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (UniqueConstraint("org_id", "name", name="uq_student_categories_org_id"),)


class Student(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "students"

    org_id: Mapped[uuid.UUID] = _org_fk()
    admission_no: Mapped[str] = mapped_column(Text, nullable=False)  # unique per org
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    # Current class. SET NULL so deleting a class doesn't cascade-delete students.
    class_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("school_classes.id", ondelete="SET NULL"), nullable=True
    )
    roll_no: Mapped[str | None] = mapped_column(Text, nullable=True)
    # V1-2 (D-13): the parent's password at portal login, and the birthday feed
    # (D-56). Nullable — the readiness report counts the gap ("45 parents cannot
    # log in"), the importer parses it tolerantly and NEVER guesses.
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    # V1-3 (S-02): attendance denominators start here for a mid-year joiner —
    # a September admission's % must not be computed over August's registers.
    enrolled_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="active")
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("student_categories.id", ondelete="SET NULL"), nullable=True
    )
    photo: Mapped[str | None] = mapped_column(Text, nullable=True)  # attachment key/url

    guardians: Mapped[list["Guardian"]] = relationship(
        "Guardian", back_populates="student", cascade="all, delete-orphan"
    )
    category: Mapped["StudentCategory | None"] = relationship("StudentCategory")

    __table_args__ = (
        UniqueConstraint("org_id", "admission_no", name="uq_students_org_id"),
        CheckConstraint("status IN ('active', 'left')", name="status_valid"),
    )


class Guardian(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "guardians"

    org_id: Mapped[uuid.UUID] = _org_fk()
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    relation: Mapped[str | None] = mapped_column(Text, nullable=True)  # "Father" / "Mother" / …
    phone: Mapped[str] = mapped_column(Text, nullable=False)  # E.164
    # Set when the guardian claims a parent login via phone OTP. SET NULL keeps
    # the guardian record if the user account is ever deleted.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    # Consent flag captured at roster import; every guardian message honours it (SPRD §7).
    notify_opt_out: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")

    student: Mapped["Student"] = relationship("Student", back_populates="guardians")


# ── the class teacher's own log about a child (founder, 2026-08-05) ──────────
# The note categories. Free-ish, but a fixed short list because the whole value
# of the log is being able to read a year of it in one scroll — forty spellings
# of "spoke to parent" is a diary, not a record.
STUDENT_NOTE_KINDS: tuple[str, ...] = (
    "general", "behaviour", "wellbeing", "achievement", "parent_contact", "concern",
)


class StudentNote(Base, UUIDPKMixin, CreatedAtMixin):
    """The class teacher's log about one child — **append-only** (law 3).

    Every other thing the school knows about a child is a byproduct of doing the
    work (P5): attendance is a tap, coverage is a lesson log, a band is a test.
    This is the one deliberate exception, and it is the class teacher's own: the
    thing she noticed that no capture surface has a field for.

    It is **staff-only** and never reaches a parent surface. `services/
    parent_portal.py` is an allowlist projection built field by field, so this
    table stays out of it by construction rather than by remembering to exclude
    it — but the rule is written here too, because the first person to add a
    "share with parent" flag needs to meet it.

    Append-only, like `fee_notes` / `plan_approvals` / `demo_request_notes`: a
    correction is a new row. What a teacher thought in September is part of the
    record even when November disagrees, and a log that can be quietly rewritten
    is not a log.
    """

    __tablename__ = "student_notes"

    org_id: Mapped[uuid.UUID] = _org_fk()
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False, server_default="general")
    note: Mapped[str] = mapped_column(Text, nullable=False)
    # SET NULL so the history outlives the account (the `fee_notes` rule).
    author_member_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memberships.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "kind IN ('general', 'behaviour', 'wellbeing', 'achievement', "
            "'parent_contact', 'concern')",
            name="ck_student_notes_kind",
        ),
    )
