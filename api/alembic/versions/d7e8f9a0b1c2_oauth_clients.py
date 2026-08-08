"""oauth_clients + oauth_grants, and the OAuth columns on api_tokens

Phase 2's OAuth half (`D-99`). Additive throughout: two new tables and five
nullable columns, so production migrates safely ahead of the code deploy.

Both new tables carry `org_id`, so law 2 applies and each gets its own
`org_isolation` policy here rather than being appended to `ORG_SCOPED_TABLES`
(which the initial migration reads live).

Revision ID: d7e8f9a0b1c2
Revises: c6d7e8f9a0b1
Create Date: 2026-08-08
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.core.rls import disable_rls_sql, enable_rls_sql

revision = "d7e8f9a0b1c2"
down_revision = "c6d7e8f9a0b1"
branch_labels = None
depends_on = None

_RLS_TABLES = ["oauth_clients", "oauth_grants"]


def upgrade() -> None:
    op.create_table(
        "oauth_clients",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("client_id", sa.Text(), nullable=False),
        sa.Column("client_secret_hash", sa.Text(), nullable=True),
        sa.Column("redirect_uris", postgresql.JSONB(), nullable=False),
        sa.Column("scopes", postgresql.JSONB(), nullable=False),
        sa.Column("mode", sa.Text(), nullable=False, server_default="read"),
        sa.Column("created_by_membership_id", postgresql.UUID(as_uuid=True),
                  nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_membership_id"], ["memberships.id"],
                                ondelete="SET NULL"),
        sa.UniqueConstraint("client_id", name="uq_oauth_clients_client_id"),
        sa.CheckConstraint("mode IN ('read', 'read_write')",
                           name="oauth_client_mode_valid"),
    )
    op.create_index("ix_oauth_clients_org", "oauth_clients", ["org_id"])

    op.create_table(
        "oauth_grants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code_hash", sa.Text(), nullable=False),
        sa.Column("redirect_uri", sa.Text(), nullable=False),
        sa.Column("resource", sa.Text(), nullable=True),
        sa.Column("scopes", postgresql.JSONB(), nullable=False),
        sa.Column("code_challenge", sa.Text(), nullable=False),
        sa.Column("code_challenge_method", sa.Text(), nullable=False,
                  server_default="S256"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["client_id"], ["oauth_clients.id"],
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["membership_id"], ["memberships.id"],
                                ondelete="CASCADE"),
        sa.UniqueConstraint("code_hash", name="uq_oauth_grants_code_hash"),
        sa.CheckConstraint("code_challenge_method = 'S256'",
                           name="oauth_grant_pkce_s256"),
    )
    op.create_index("ix_oauth_grants_org", "oauth_grants", ["org_id"])
    op.create_index("ix_oauth_grants_client", "oauth_grants", ["client_id"])

    # An OAuth access token is an api_tokens row — one token store, one resolver.
    op.add_column("api_tokens", sa.Column(
        "oauth_client_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("api_tokens", sa.Column(
        "grant_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("api_tokens", sa.Column(
        "refresh_token_hash", sa.Text(), nullable=True))
    op.add_column("api_tokens", sa.Column(
        "refresh_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("api_tokens", sa.Column("audience", sa.Text(), nullable=True))
    op.create_foreign_key("fk_api_tokens_oauth_client", "api_tokens",
                          "oauth_clients", ["oauth_client_id"], ["id"],
                          ondelete="CASCADE")
    op.create_unique_constraint("uq_api_tokens_refresh_hash", "api_tokens",
                                ["refresh_token_hash"])
    op.create_index("ix_api_tokens_oauth_client", "api_tokens",
                    ["oauth_client_id"])

    for stmt in enable_rls_sql(_RLS_TABLES):
        op.execute(stmt)


def downgrade() -> None:
    for stmt in disable_rls_sql(_RLS_TABLES):
        op.execute(stmt)
    op.drop_index("ix_api_tokens_oauth_client", table_name="api_tokens")
    op.drop_constraint("uq_api_tokens_refresh_hash", "api_tokens", type_="unique")
    op.drop_constraint("fk_api_tokens_oauth_client", "api_tokens",
                       type_="foreignkey")
    for col in ("audience", "refresh_expires_at", "refresh_token_hash",
                "grant_id", "oauth_client_id"):
        op.drop_column("api_tokens", col)
    op.drop_index("ix_oauth_grants_client", table_name="oauth_grants")
    op.drop_index("ix_oauth_grants_org", table_name="oauth_grants")
    op.drop_table("oauth_grants")
    op.drop_index("ix_oauth_clients_org", table_name="oauth_clients")
    op.drop_table("oauth_clients")
