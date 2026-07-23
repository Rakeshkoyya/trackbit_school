"""demo_requests: public "book a demo" leads from the marketing site

Platform-level, like `users`: a lead arrives before the school has an org, so
there is no org_id to isolate on and therefore no RLS policy (law 2 applies to
org-scoped business data). Reads are gated at the app layer by
`require_super_admin`.

Revision ID: a2b3c4d5e6f7
Revises: fe5f6a7b8c9d
Create Date: 2026-07-23 10:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a2b3c4d5e6f7"
down_revision: str | None = "fe5f6a7b8c9d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "demo_requests",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("school_name", sa.Text(), nullable=False),
        sa.Column("contact_name", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("phone", sa.Text(), nullable=False),
        sa.Column("city", sa.Text(), nullable=True),
        sa.Column("student_count", sa.Integer(), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("source", sa.Text(), server_default="landing", nullable=False),
        sa.Column("status", sa.Text(), server_default="new", nullable=False),
        sa.CheckConstraint("status IN ('new', 'contacted', 'scheduled', 'won', 'lost')",
                           name=op.f("ck_demo_requests_status_valid")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_demo_requests")),
    )
    op.create_index(op.f("ix_demo_requests_created_at"), "demo_requests", ["created_at"])


def downgrade() -> None:
    op.drop_index(op.f("ix_demo_requests_created_at"), table_name="demo_requests")
    op.drop_table("demo_requests")
