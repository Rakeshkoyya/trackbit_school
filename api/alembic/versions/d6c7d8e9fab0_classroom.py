"""classroom capture: lesson_logs + homework (SPRD §4.4, M2)

Revision ID: d6c7d8e9fab0
Revises: d5b6c7d8e9fa
Create Date: 2026-07-07 14:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.rls import SCHOOL_CLASSROOM_TABLES, disable_rls_sql, enable_rls_sql

revision: str = "d6c7d8e9fab0"
down_revision: str | None = "d5b6c7d8e9fa"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "lesson_logs",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("class_subject_id", sa.UUID(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("member_id", sa.UUID(), nullable=True),
        sa.Column("topic_id", sa.UUID(), nullable=True),
        sa.Column("coverage", sa.Text(), server_default="full", nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("coverage IN ('full', 'partial')", name=op.f("ck_lesson_logs_coverage_valid")),
        sa.ForeignKeyConstraint(["class_subject_id"], ["class_subjects.id"], name=op.f("fk_lesson_logs_class_subject_id_class_subjects"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["member_id"], ["memberships.id"], name=op.f("fk_lesson_logs_member_id_memberships"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], name=op.f("fk_lesson_logs_org_id_organizations"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["topic_id"], ["syllabus_topics.id"], name=op.f("fk_lesson_logs_topic_id_syllabus_topics"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lesson_logs")),
        sa.UniqueConstraint("class_subject_id", "date", "topic_id", name=op.f("uq_lesson_logs_class_subject_id")),
    )
    op.create_index(op.f("ix_lesson_logs_class_subject_id"), "lesson_logs", ["class_subject_id"])
    op.create_index(op.f("ix_lesson_logs_org_id"), "lesson_logs", ["org_id"])

    op.create_table(
        "homework_assignments",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("class_subject_id", sa.UUID(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["class_subject_id"], ["class_subjects.id"], name=op.f("fk_homework_assignments_class_subject_id_class_subjects"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], name=op.f("fk_homework_assignments_org_id_organizations"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_homework_assignments")),
    )
    op.create_index(op.f("ix_homework_assignments_class_subject_id"), "homework_assignments", ["class_subject_id"])
    op.create_index(op.f("ix_homework_assignments_org_id"), "homework_assignments", ["org_id"])

    op.create_table(
        "homework_checks",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("assignment_id", sa.UUID(), nullable=False),
        sa.Column("done_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["assignment_id"], ["homework_assignments.id"], name=op.f("fk_homework_checks_assignment_id_homework_assignments"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], name=op.f("fk_homework_checks_org_id_organizations"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_homework_checks")),
    )
    op.create_index(op.f("ix_homework_checks_assignment_id"), "homework_checks", ["assignment_id"])
    op.create_index(op.f("ix_homework_checks_org_id"), "homework_checks", ["org_id"])

    for stmt in enable_rls_sql(SCHOOL_CLASSROOM_TABLES):
        op.execute(stmt)


def downgrade() -> None:
    for stmt in disable_rls_sql(SCHOOL_CLASSROOM_TABLES):
        op.execute(stmt)
    for table in ("homework_checks", "homework_assignments", "lesson_logs"):
        op.drop_table(table)
