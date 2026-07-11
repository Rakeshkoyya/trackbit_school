"""After-school & hostel sessions (M2 + HS-1, SPRD §4.4) — the evening timetable.

NOT school-wide attendance registers (§8 fence): a session is a specific recurring
block with its own roster. Since HS-1 a session is also the hostel-timetable unit:
admin-planned, optionally spanning whole classes (`session_classes` — the roster is
*computed*, so a newly admitted hosteller appears with zero admin work), typed by
`kind` — study (optional per-student logs), homework (computed homework board),
activity (photo/video memories in `session_media`, attached to the meeting, never
to a student — P5).
"""

import uuid
from datetime import date

from sqlalchemy import (
    BigInteger,
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
    # End of the block ("17:30") — draws the hostel week grid and feeds the
    # deterministic teacher-clash check. NULL = open-ended.
    end_time: Mapped[str | None] = mapped_column(Text, nullable=True)
    # study = evening prep (optional per-student logs) · homework = homework board
    # · activity = yoga/boxing/… (memories only).
    kind: Mapped[str] = mapped_column(Text, nullable=False, server_default="study")
    # When class-linked: restrict the computed roster to the "Hosteller" category.
    hostellers_only: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    students: Mapped[list["SessionStudent"]] = relationship(
        back_populates="session", cascade="all, delete-orphan")
    classes: Mapped[list["SessionClass"]] = relationship(
        back_populates="session", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("kind IN ('study', 'homework', 'activity')", name="kind_valid"),
    )


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


class SessionClass(Base, UUIDPKMixin):
    """Class-level membership (HS-1): the session includes every active student of
    the class (optionally hostellers only). Ad-hoc additions stay in
    `session_students`; the effective roster is the computed union."""

    __tablename__ = "session_classes"

    org_id: Mapped[uuid.UUID] = _org_fk()
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("school_classes.id", ondelete="CASCADE"), nullable=False
    )

    session: Mapped["Session"] = relationship(back_populates="classes")

    __table_args__ = (
        UniqueConstraint("session_id", "class_id", name="uq_session_classes_session_id"),
    )


class SessionMeeting(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "session_meetings"

    org_id: Mapped[uuid.UUID] = _org_fk()
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    # Legacy single batch photo (pre-HS-1). New media lands in session_media.
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


class SessionMedia(Base, UUIDPKMixin, CreatedAtMixin):
    """Memories of a meeting (HS-1): photos/videos in R2. Stores the object *key*,
    never a URL — presigned GET URLs expire; the API mints fetch URLs at read time.
    Media belongs to the meeting, never to a student (P5: batch evidence only)."""

    __tablename__ = "session_media"

    org_id: Mapped[uuid.UUID] = _org_fk()
    meeting_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("session_meetings.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False)  # photo | video
    object_key: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_by_member_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memberships.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        CheckConstraint("kind IN ('photo', 'video')", name="media_kind_valid"),
    )


class SessionStudentLog(Base, UUIDPKMixin, CreatedAtMixin):
    """Optional per-student study-session note (HS-1): what this student worked on
    tonight. One row per (meeting, student), upserted. NEVER mandatory — attendance
    stays the ≤60s tap flow; a row exists only when there is something to say
    (P1v2: no mandatory per-student capture)."""

    __tablename__ = "session_student_logs"

    org_id: Mapped[uuid.UUID] = _org_fk()
    meeting_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("session_meetings.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False
    )
    subject_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True
    )
    note: Mapped[str] = mapped_column(Text, nullable=False)
    member_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memberships.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("meeting_id", "student_id", name="uq_session_student_logs_meeting_id"),
    )
