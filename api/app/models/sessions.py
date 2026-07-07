"""After-school sessions (M2, SPRD §4.4) — teacher-run remedial/homework classes.

NOT school-wide attendance registers (§8 fence): a session is a specific recurring
class with its own roster. The record assembles itself — one batch photo per
meeting as evidence, never one per student (P1/P5).
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
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )


class Session(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "sessions"

    org_id: Mapped[uuid.UUID] = _org_fk()
    name: Mapped[str] = mapped_column(Text, nullable=False)  # "Homework Class 6A"
    owner_member_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memberships.id", ondelete="SET NULL"), nullable=True
    )
    weekdays: Mapped[list[int]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    time: Mapped[str | None] = mapped_column(Text, nullable=True)  # "16:15"
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    students: Mapped[list["SessionStudent"]] = relationship(
        back_populates="session", cascade="all, delete-orphan")


class SessionStudent(Base, UUIDPKMixin):
    __tablename__ = "session_students"

    org_id: Mapped[uuid.UUID] = _org_fk()
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False
    )

    session: Mapped["Session"] = relationship(back_populates="students")

    __table_args__ = (
        UniqueConstraint("session_id", "student_id", name="uq_session_students_session_id"),
    )


class SessionMeeting(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "session_meetings"

    org_id: Mapped[uuid.UUID] = _org_fk()
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    # One batch photo of the pile of work — evidence for the whole meeting (P5).
    evidence_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("session_id", "date", name="uq_session_meetings_session_id"),
    )


class SessionAttendance(Base, UUIDPKMixin):
    __tablename__ = "session_attendance"

    org_id: Mapped[uuid.UUID] = _org_fk()
    meeting_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("session_meetings.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="present")
    late_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    homework_done: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    __table_args__ = (
        UniqueConstraint("meeting_id", "student_id", name="uq_session_attendance_meeting_id"),
        CheckConstraint("status IN ('present', 'late', 'absent')", name="status_valid"),
    )
