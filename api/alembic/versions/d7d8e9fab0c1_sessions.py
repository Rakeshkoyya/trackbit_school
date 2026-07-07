"""after-school sessions: sessions/students/meetings/attendance (SPRD §4.4, M2)

Revision ID: d7d8e9fab0c1
Revises: d6c7d8e9fab0
Create Date: 2026-07-07 14:30:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.core.rls import SCHOOL_SESSION_TABLES, disable_rls_sql, enable_rls_sql

revision: str = "d7d8e9fab0c1"
down_revision: str | None = "d6c7d8e9fab0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sessions",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("owner_member_id", sa.UUID(), nullable=True),
        sa.Column("weekdays", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("time", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], name=op.f("fk_sessions_org_id_organizations"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_member_id"], ["memberships.id"], name=op.f("fk_sessions_owner_member_id_memberships"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sessions")),
    )
    op.create_index(op.f("ix_sessions_org_id"), "sessions", ["org_id"])

    op.create_table(
        "session_students",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column("student_id", sa.UUID(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], name=op.f("fk_session_students_org_id_organizations"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], name=op.f("fk_session_students_session_id_sessions"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], name=op.f("fk_session_students_student_id_students"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_session_students")),
        sa.UniqueConstraint("session_id", "student_id", name=op.f("uq_session_students_session_id")),
    )
    op.create_index(op.f("ix_session_students_org_id"), "session_students", ["org_id"])
    op.create_index(op.f("ix_session_students_session_id"), "session_students", ["session_id"])

    op.create_table(
        "session_meetings",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("evidence_url", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], name=op.f("fk_session_meetings_org_id_organizations"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], name=op.f("fk_session_meetings_session_id_sessions"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_session_meetings")),
        sa.UniqueConstraint("session_id", "date", name=op.f("uq_session_meetings_session_id")),
    )
    op.create_index(op.f("ix_session_meetings_org_id"), "session_meetings", ["org_id"])
    op.create_index(op.f("ix_session_meetings_session_id"), "session_meetings", ["session_id"])

    op.create_table(
        "session_attendance",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("meeting_id", sa.UUID(), nullable=False),
        sa.Column("student_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.Text(), server_default="present", nullable=False),
        sa.Column("late_minutes", sa.Integer(), nullable=True),
        sa.Column("homework_done", sa.Boolean(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint("status IN ('present', 'late', 'absent')", name=op.f("ck_session_attendance_status_valid")),
        sa.ForeignKeyConstraint(["meeting_id"], ["session_meetings.id"], name=op.f("fk_session_attendance_meeting_id_session_meetings"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], name=op.f("fk_session_attendance_org_id_organizations"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], name=op.f("fk_session_attendance_student_id_students"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_session_attendance")),
        sa.UniqueConstraint("meeting_id", "student_id", name=op.f("uq_session_attendance_meeting_id")),
    )
    op.create_index(op.f("ix_session_attendance_meeting_id"), "session_attendance", ["meeting_id"])
    op.create_index(op.f("ix_session_attendance_org_id"), "session_attendance", ["org_id"])

    for stmt in enable_rls_sql(SCHOOL_SESSION_TABLES):
        op.execute(stmt)


def downgrade() -> None:
    for stmt in disable_rls_sql(SCHOOL_SESSION_TABLES):
        op.execute(stmt)
    for table in ("session_attendance", "session_meetings", "session_students", "sessions"):
        op.drop_table(table)
