"""daily_reports (V2-P4, SPRD2 §4.4/§5.6)

Revision ID: f3d4e5f6a7b8
Revises: f2c3d4e5f6a7
Create Date: 2026-07-08 13:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.core.rls import SCHOOL_REPORT_TABLES, disable_rls_sql, enable_rls_sql

revision: str = "f3d4e5f6a7b8"
down_revision: str | None = "f2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "daily_reports",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("for_date", sa.Date(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content_md", sa.Text(), server_default="", nullable=False),
        sa.Column("highlights", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("status", sa.Text(), server_default="draft", nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], name=op.f("fk_daily_reports_org_id_organizations"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_daily_reports")),
        sa.UniqueConstraint("org_id", "for_date", name="uq_daily_reports_org_date"),
        sa.CheckConstraint("status IN ('draft', 'final')", name=op.f("ck_daily_reports_status_valid")),
    )
    op.create_index(op.f("ix_daily_reports_org_id"), "daily_reports", ["org_id"])

    for stmt in enable_rls_sql(SCHOOL_REPORT_TABLES):
        op.execute(stmt)


def downgrade() -> None:
    for stmt in disable_rls_sql(SCHOOL_REPORT_TABLES):
        op.execute(stmt)
    op.drop_table("daily_reports")
