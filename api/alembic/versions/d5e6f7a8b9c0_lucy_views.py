"""GA-1 composed views: lucy_views (self-contained widget compositions)

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-07-24 12:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

from app.core.rls import SCHOOL_LUCY_VIEW_TABLES, disable_rls_sql, enable_rls_sql

revision: str = "d5e6f7a8b9c0"
down_revision: str | None = "c4d5e6f7a8b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "lucy_views",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("membership_id", sa.UUID(), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("layout", JSONB(), server_default="{}", nullable=False),
        sa.Column("widgets", JSONB(), server_default="[]", nullable=False),
        sa.Column("signature", sa.Text(), server_default="", nullable=False),
        sa.Column("refreshed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], name=op.f("fk_lucy_views_org_id_organizations"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["membership_id"], ["memberships.id"], name=op.f("fk_lucy_views_membership_id_memberships"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["conversation_id"], ["lucy_conversations.id"], name=op.f("fk_lucy_views_conversation_id_lucy_conversations"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lucy_views")),
    )
    op.create_index(op.f("ix_lucy_views_org_id"), "lucy_views", ["org_id"])
    op.create_index("ix_lucy_views_member_created", "lucy_views",
                    ["org_id", "membership_id", "created_at"])

    for stmt in enable_rls_sql(SCHOOL_LUCY_VIEW_TABLES):
        op.execute(stmt)


def downgrade() -> None:
    for stmt in disable_rls_sql(SCHOOL_LUCY_VIEW_TABLES):
        op.execute(stmt)
    op.drop_table("lucy_views")
