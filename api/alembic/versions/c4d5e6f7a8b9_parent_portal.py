"""parent portal: guardian logins via phone OTP

Founder decision 2026-07-23: guardians get a read-only login (supersedes the
"no parent login" fence; P4 still holds — the parent surface never carries
band/tier data, enforced in the parent projection layer + tests).

- guardians.user_id: set when a guardian claims their login (phone OTP match).
- otp_codes: pre-identity OTP store keyed by normalized phone. Platform-level
  like demo_requests — no org_id (one phone may span orgs), no RLS policy;
  access is app-layer only.
- organizations.parent_portal_enabled: per-school rollout switch.

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-07-23 18:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c4d5e6f7a8b9"
down_revision: str | None = "b3c4d5e6f7a8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "guardians",
        sa.Column("user_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_guardians_user_id_users"), "guardians", "users",
        ["user_id"], ["id"], ondelete="SET NULL",
    )
    op.create_index(op.f("ix_guardians_user_id"), "guardians", ["user_id"])

    op.create_table(
        "otp_codes",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("phone_key", sa.Text(), nullable=False),
        sa.Column("code_hash", sa.Text(), nullable=False),
        sa.Column("purpose", sa.Text(), server_default="parent_login", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_otp_codes")),
    )
    op.create_index(op.f("ix_otp_codes_phone_key"), "otp_codes", ["phone_key"])

    op.add_column(
        "organizations",
        sa.Column("parent_portal_enabled", sa.Boolean(),
                  server_default=sa.text("true"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("organizations", "parent_portal_enabled")
    op.drop_index(op.f("ix_otp_codes_phone_key"), table_name="otp_codes")
    op.drop_table("otp_codes")
    op.drop_index(op.f("ix_guardians_user_id"), table_name="guardians")
    op.drop_constraint(op.f("fk_guardians_user_id_users"), "guardians", type_="foreignkey")
    op.drop_column("guardians", "user_id")
