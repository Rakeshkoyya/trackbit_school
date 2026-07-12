"""Lucy agentic chat: conversations, messages, widgets, pending actions

Revision ID: fc3d4e5f6a7b
Revises: fb2c3d4e5f6a
Create Date: 2026-07-12 12:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

from app.core.rls import SCHOOL_LUCY_TABLES, disable_rls_sql, enable_rls_sql

revision: str = "fc3d4e5f6a7b"
down_revision: str | None = "fb2c3d4e5f6a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "lucy_conversations",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("membership_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], name=op.f("fk_lucy_conversations_org_id_organizations"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["membership_id"], ["memberships.id"], name=op.f("fk_lucy_conversations_membership_id_memberships"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lucy_conversations")),
    )
    op.create_index(op.f("ix_lucy_conversations_org_id"), "lucy_conversations", ["org_id"])
    op.create_index("ix_lucy_conversations_member_updated", "lucy_conversations",
                    ["org_id", "membership_id", "updated_at"])

    op.create_table(
        "lucy_messages",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), server_default="", nullable=False),
        sa.Column("meta", JSONB(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], name=op.f("fk_lucy_messages_org_id_organizations"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["conversation_id"], ["lucy_conversations.id"], name=op.f("fk_lucy_messages_conversation_id_lucy_conversations"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lucy_messages")),
        sa.CheckConstraint("role IN ('user', 'assistant')", name=op.f("ck_lucy_messages_role_valid")),
    )
    op.create_index(op.f("ix_lucy_messages_org_id"), "lucy_messages", ["org_id"])
    op.create_index(op.f("ix_lucy_messages_conversation_id"), "lucy_messages", ["conversation_id"])

    op.create_table(
        "lucy_widgets",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("message_id", sa.UUID(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), server_default="", nullable=False),
        sa.Column("spec_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("payload", JSONB(), server_default="{}", nullable=False),
        sa.Column("source_tool", sa.Text(), nullable=True),
        sa.Column("source_params", JSONB(), nullable=True),
        sa.Column("pinned", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("pinned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("refreshed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], name=op.f("fk_lucy_widgets_org_id_organizations"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["conversation_id"], ["lucy_conversations.id"], name=op.f("fk_lucy_widgets_conversation_id_lucy_conversations"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["message_id"], ["lucy_messages.id"], name=op.f("fk_lucy_widgets_message_id_lucy_messages"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lucy_widgets")),
    )
    op.create_index(op.f("ix_lucy_widgets_org_id"), "lucy_widgets", ["org_id"])
    op.create_index(op.f("ix_lucy_widgets_conversation_id"), "lucy_widgets", ["conversation_id"])
    op.create_index("ix_lucy_widgets_pinned", "lucy_widgets", ["org_id", "pinned"],
                    postgresql_where=sa.text("pinned"))

    op.create_table(
        "lucy_pending_actions",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("message_id", sa.UUID(), nullable=True),
        sa.Column("membership_id", sa.UUID(), nullable=False),
        sa.Column("tool", sa.Text(), nullable=False),
        sa.Column("params", JSONB(), server_default="{}", nullable=False),
        sa.Column("summary", sa.Text(), server_default="", nullable=False),
        sa.Column("status", sa.Text(), server_default="proposed", nullable=False),
        sa.Column("result", JSONB(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], name=op.f("fk_lucy_pending_actions_org_id_organizations"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["conversation_id"], ["lucy_conversations.id"], name=op.f("fk_lucy_pending_actions_conversation_id_lucy_conversations"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["message_id"], ["lucy_messages.id"], name=op.f("fk_lucy_pending_actions_message_id_lucy_messages"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["membership_id"], ["memberships.id"], name=op.f("fk_lucy_pending_actions_membership_id_memberships"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lucy_pending_actions")),
        sa.CheckConstraint(
            "status IN ('proposed', 'executed', 'failed', 'cancelled', 'expired')",
            name=op.f("ck_lucy_pending_actions_status_valid")),
    )
    op.create_index(op.f("ix_lucy_pending_actions_org_id"), "lucy_pending_actions", ["org_id"])
    op.create_index(op.f("ix_lucy_pending_actions_conversation_id"), "lucy_pending_actions", ["conversation_id"])

    for stmt in enable_rls_sql(SCHOOL_LUCY_TABLES):
        op.execute(stmt)


def downgrade() -> None:
    for stmt in disable_rls_sql(SCHOOL_LUCY_TABLES):
        op.execute(stmt)
    op.drop_table("lucy_pending_actions")
    op.drop_table("lucy_widgets")
    op.drop_table("lucy_messages")
    op.drop_table("lucy_conversations")
