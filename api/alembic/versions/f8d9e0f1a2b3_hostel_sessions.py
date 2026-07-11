"""hostel sessions (HS-1)

Promotes the after-school sessions module into the hostel timetable unit.

`sessions` gains `kind` (study | homework | activity — drives the capture surface),
`end_time` (so a week grid can be drawn and teacher clashes detected), and
`hostellers_only` (class-linked rosters filtered to the Hosteller category).
Existing rows default to kind='study' and behave exactly as before.

Three new tables:
- `session_classes` — class-level membership; the effective roster is computed
  (class students ∪ explicit session_students), never materialized.
- `session_media`   — photos/videos of a meeting ("memories"), stored as R2 object
  *keys* (URLs are minted at read time; presigned GETs expire). Media attaches to
  the meeting, never a student (P5).
- `session_student_logs` — optional per-student study note, one row per
  (meeting, student). Optional by design: P1v2 forbids mandatory per-student capture.

Revision ID: f8d9e0f1a2b3
Revises: a8b9c0d1e2f3
Create Date: 2026-07-11 10:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.rls import SCHOOL_HOSTEL_TABLES, disable_rls_sql, enable_rls_sql

revision: str = "f8d9e0f1a2b3"
down_revision: str | None = "a8b9c0d1e2f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("sessions", sa.Column("end_time", sa.Text(), nullable=True))
    op.add_column("sessions", sa.Column("kind", sa.Text(), nullable=False,
                                        server_default="study"))
    op.add_column("sessions", sa.Column("hostellers_only", sa.Boolean(), nullable=False,
                                        server_default="false"))
    op.create_check_constraint("ck_sessions_kind_valid", "sessions",
                               "kind IN ('study', 'homework', 'activity')")

    op.create_table(
        "session_classes",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column("class_id", sa.UUID(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"],
                                name=op.f("fk_session_classes_org_id_organizations"),
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"],
                                name=op.f("fk_session_classes_session_id_sessions"),
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["class_id"], ["school_classes.id"],
                                name=op.f("fk_session_classes_class_id_school_classes"),
                                ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_session_classes")),
        sa.UniqueConstraint("session_id", "class_id",
                            name=op.f("uq_session_classes_session_id")),
    )
    op.create_index(op.f("ix_session_classes_org_id"), "session_classes", ["org_id"])
    op.create_index(op.f("ix_session_classes_session_id"), "session_classes", ["session_id"])

    op.create_table(
        "session_media",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("meeting_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("object_key", sa.Text(), nullable=False),
        sa.Column("content_type", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("uploaded_by_member_id", sa.UUID(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
                  nullable=False),
        sa.CheckConstraint("kind IN ('photo', 'video')",
                           name=op.f("ck_session_media_media_kind_valid")),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"],
                                name=op.f("fk_session_media_org_id_organizations"),
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["meeting_id"], ["session_meetings.id"],
                                name=op.f("fk_session_media_meeting_id_session_meetings"),
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by_member_id"], ["memberships.id"],
                                name=op.f("fk_session_media_uploaded_by_member_id_memberships"),
                                ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_session_media")),
    )
    op.create_index(op.f("ix_session_media_org_id"), "session_media", ["org_id"])
    op.create_index(op.f("ix_session_media_meeting_id"), "session_media", ["meeting_id"])

    op.create_table(
        "session_student_logs",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("meeting_id", sa.UUID(), nullable=False),
        sa.Column("student_id", sa.UUID(), nullable=False),
        sa.Column("subject_id", sa.UUID(), nullable=True),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("member_id", sa.UUID(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
                  nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"],
                                name=op.f("fk_session_student_logs_org_id_organizations"),
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["meeting_id"], ["session_meetings.id"],
                                name=op.f("fk_session_student_logs_meeting_id_session_meetings"),
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"],
                                name=op.f("fk_session_student_logs_student_id_students"),
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"],
                                name=op.f("fk_session_student_logs_subject_id_subjects"),
                                ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["member_id"], ["memberships.id"],
                                name=op.f("fk_session_student_logs_member_id_memberships"),
                                ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_session_student_logs")),
        sa.UniqueConstraint("meeting_id", "student_id",
                            name=op.f("uq_session_student_logs_meeting_id")),
    )
    op.create_index(op.f("ix_session_student_logs_org_id"), "session_student_logs", ["org_id"])
    op.create_index(op.f("ix_session_student_logs_meeting_id"), "session_student_logs",
                    ["meeting_id"])

    for stmt in enable_rls_sql(SCHOOL_HOSTEL_TABLES):
        op.execute(stmt)


def downgrade() -> None:
    for stmt in disable_rls_sql(SCHOOL_HOSTEL_TABLES):
        op.execute(stmt)
    op.drop_table("session_student_logs")
    op.drop_table("session_media")
    op.drop_table("session_classes")
    op.drop_constraint("ck_sessions_kind_valid", "sessions", type_="check")
    op.drop_column("sessions", "hostellers_only")
    op.drop_column("sessions", "kind")
    op.drop_column("sessions", "end_time")
