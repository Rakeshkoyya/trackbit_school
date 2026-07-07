"""syllabus units/topics + plans/plan_entries (SPRD §4.3, M1)

Revision ID: d5b6c7d8e9fa
Revises: d4a5b6c7d8e9
Create Date: 2026-07-07 13:30:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.rls import SCHOOL_SYLLABUS_TABLES, disable_rls_sql, enable_rls_sql

revision: str = "d5b6c7d8e9fa"
down_revision: str | None = "d4a5b6c7d8e9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "syllabus_units",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("class_subject_id", sa.UUID(), nullable=False),
        sa.Column("position", sa.Integer(), server_default="0", nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["class_subject_id"], ["class_subjects.id"], name=op.f("fk_syllabus_units_class_subject_id_class_subjects"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], name=op.f("fk_syllabus_units_org_id_organizations"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_syllabus_units")),
    )
    op.create_index(op.f("ix_syllabus_units_class_subject_id"), "syllabus_units", ["class_subject_id"])
    op.create_index(op.f("ix_syllabus_units_org_id"), "syllabus_units", ["org_id"])

    op.create_table(
        "syllabus_topics",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("unit_id", sa.UUID(), nullable=False),
        sa.Column("position", sa.Integer(), server_default="0", nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("est_periods", sa.Integer(), server_default="1", nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], name=op.f("fk_syllabus_topics_org_id_organizations"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["unit_id"], ["syllabus_units.id"], name=op.f("fk_syllabus_topics_unit_id_syllabus_units"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_syllabus_topics")),
    )
    op.create_index(op.f("ix_syllabus_topics_org_id"), "syllabus_topics", ["org_id"])
    op.create_index(op.f("ix_syllabus_topics_unit_id"), "syllabus_topics", ["unit_id"])

    op.create_table(
        "plans",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("class_subject_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.Text(), server_default="draft", nullable=False),
        sa.Column("approved_by", sa.UUID(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"], name=op.f("fk_plans_approved_by_users"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["class_subject_id"], ["class_subjects.id"], name=op.f("fk_plans_class_subject_id_class_subjects"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], name=op.f("fk_plans_org_id_organizations"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_plans")),
        sa.UniqueConstraint("class_subject_id", name=op.f("uq_plans_class_subject_id")),
    )
    op.create_index(op.f("ix_plans_org_id"), "plans", ["org_id"])

    op.create_table(
        "plan_entries",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("class_subject_id", sa.UUID(), nullable=False),
        sa.Column("topic_id", sa.UUID(), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["class_subject_id"], ["class_subjects.id"], name=op.f("fk_plan_entries_class_subject_id_class_subjects"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], name=op.f("fk_plan_entries_org_id_organizations"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["topic_id"], ["syllabus_topics.id"], name=op.f("fk_plan_entries_topic_id_syllabus_topics"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_plan_entries")),
        sa.UniqueConstraint("class_subject_id", "topic_id", name=op.f("uq_plan_entries_class_subject_id")),
    )
    op.create_index(op.f("ix_plan_entries_class_subject_id"), "plan_entries", ["class_subject_id"])
    op.create_index(op.f("ix_plan_entries_org_id"), "plan_entries", ["org_id"])

    for stmt in enable_rls_sql(SCHOOL_SYLLABUS_TABLES):
        op.execute(stmt)


def downgrade() -> None:
    for stmt in disable_rls_sql(SCHOOL_SYLLABUS_TABLES):
        op.execute(stmt)
    for table in ("plan_entries", "plans", "syllabus_topics", "syllabus_units"):
        op.drop_table(table)
