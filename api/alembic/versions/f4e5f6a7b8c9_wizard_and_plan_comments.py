"""onboarding_state + plan_comments (V2-P5, SPRD2 §4.4/§5.1/§5.2)

Revision ID: f4e5f6a7b8c9
Revises: f3d4e5f6a7b8
Create Date: 2026-07-08 14:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.core.rls import SCHOOL_WIZARD_TABLES, disable_rls_sql, enable_rls_sql

revision: str = "f4e5f6a7b8c9"
down_revision: str | None = "f3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "onboarding_state",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("current_step", sa.Integer(), server_default="1", nullable=False),
        sa.Column("payload", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("status", sa.Text(), server_default="in_progress", nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], name=op.f("fk_onboarding_state_org_id_organizations"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_onboarding_state")),
        sa.UniqueConstraint("org_id", name="uq_onboarding_state_org"),
        sa.CheckConstraint("status IN ('in_progress', 'done')", name=op.f("ck_onboarding_state_status_valid")),
    )
    op.create_index(op.f("ix_onboarding_state_org_id"), "onboarding_state", ["org_id"])

    op.create_table(
        "plan_comments",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("class_subject_id", sa.UUID(), nullable=False),
        sa.Column("topic_id", sa.UUID(), nullable=True),
        sa.Column("author_member_id", sa.UUID(), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default="open", nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["author_member_id"], ["memberships.id"], name=op.f("fk_plan_comments_author_member_id_memberships"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["class_subject_id"], ["class_subjects.id"], name=op.f("fk_plan_comments_class_subject_id_class_subjects"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], name=op.f("fk_plan_comments_org_id_organizations"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["topic_id"], ["syllabus_topics.id"], name=op.f("fk_plan_comments_topic_id_syllabus_topics"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_plan_comments")),
        sa.CheckConstraint("status IN ('open', 'resolved')", name=op.f("ck_plan_comments_plan_comment_status_valid")),
    )
    op.create_index(op.f("ix_plan_comments_org_id"), "plan_comments", ["org_id"])
    op.create_index(op.f("ix_plan_comments_class_subject_id"), "plan_comments", ["class_subject_id"])

    for stmt in enable_rls_sql(SCHOOL_WIZARD_TABLES):
        op.execute(stmt)


def downgrade() -> None:
    for stmt in disable_rls_sql(SCHOOL_WIZARD_TABLES):
        op.execute(stmt)
    op.drop_table("plan_comments")
    op.drop_table("onboarding_state")
