"""Students, guardians, and fee categories (SPRD §4.2).

The single student master used by fees, academics, sessions, and assessments —
no second roster, no sync hell (SPRD §2.2). Guardians are records only: parents
have no login in v1 and receive outbound notifications only (SPRD §3.4).
"""

import uuid

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Text, UniqueConstraint
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
