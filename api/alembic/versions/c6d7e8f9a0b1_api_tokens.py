"""api_tokens + organizations.agent_access — agent connector credentials

Phase 2 of the agent tool platform (`D-97`, `D-103`). Additive throughout: one
new table, and one column with a server default, so production can migrate
before the code that reads it deploys.

`api_tokens` carries `org_id`, so law 2 applies — the org-isolation policy is
engaged here, in this module's own migration, exactly as every school module
does. It is deliberately *not* appended to `ORG_SCOPED_TABLES`, which the
initial migration reads live.

Revision ID: c6d7e8f9a0b1
Revises: b5c6d7e8f9a0
Create Date: 2026-08-08
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.core.rls import disable_rls_sql, enable_rls_sql

revision = "c6d7e8f9a0b1"
down_revision = "b5c6d7e8f9a0"
branch_labels = None
depends_on = None

_RLS_TABLES = ["api_tokens"]


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("agent_access", sa.Text(), nullable=False, server_default="off"),
    )
    op.create_check_constraint(
        "agent_access_valid",
        "organizations",
        "agent_access IN ('off', 'admins', 'all_staff')",
    )

    op.create_table(
        "api_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("prefix", sa.Text(), nullable=False),
        sa.Column("scopes", postgresql.JSONB(), nullable=False),
        sa.Column("mode", sa.Text(), nullable=False, server_default="read"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_ip", sa.Text(), nullable=True),
        sa.Column("created_by_membership_id", postgresql.UUID(as_uuid=True),
                  nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by_membership_id", postgresql.UUID(as_uuid=True),
                  nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["membership_id"], ["memberships.id"],
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_membership_id"], ["memberships.id"],
                                ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["revoked_by_membership_id"], ["memberships.id"],
                                ondelete="SET NULL"),
        sa.UniqueConstraint("token_hash", name="uq_api_tokens_token_hash"),
        sa.CheckConstraint("mode IN ('read', 'read_write')",
                           name="api_token_mode_valid"),
    )
    op.create_index("ix_api_tokens_org", "api_tokens", ["org_id"])
    op.create_index("ix_api_tokens_membership", "api_tokens", ["membership_id"])

    for stmt in enable_rls_sql(_RLS_TABLES):
        op.execute(stmt)


def downgrade() -> None:
    for stmt in disable_rls_sql(_RLS_TABLES):
        op.execute(stmt)
    op.drop_index("ix_api_tokens_membership", table_name="api_tokens")
    op.drop_index("ix_api_tokens_org", table_name="api_tokens")
    op.drop_table("api_tokens")
    op.drop_constraint("agent_access_valid", "organizations", type_="check")
    op.drop_column("organizations", "agent_access")
