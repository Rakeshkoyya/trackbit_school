"""calendar events + working weekdays on academic_years (SPRD §4.3, M1)

Revision ID: d4a5b6c7d8e9
Revises: d3f4a5b6c7d8
Create Date: 2026-07-07 13:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.core.rls import SCHOOL_PLANNER_TABLES, disable_rls_sql, enable_rls_sql

revision: str = "d4a5b6c7d8e9"
down_revision: str | None = "d3f4a5b6c7d8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "academic_years",
        sa.Column("working_weekdays", postgresql.JSONB(astext_type=sa.Text()),
                  server_default=sa.text("'[0, 1, 2, 3, 4, 5]'::jsonb"), nullable=False),
    )
    op.create_table(
        "calendar_events",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("academic_year_id", sa.UUID(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("affects_teaching", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("type IN ('holiday', 'exam_block', 'event', 'celebration')", name=op.f("ck_calendar_events_type_valid")),
        sa.ForeignKeyConstraint(["academic_year_id"], ["academic_years.id"], name=op.f("fk_calendar_events_academic_year_id_academic_years"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], name=op.f("fk_calendar_events_org_id_organizations"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_calendar_events")),
    )
    op.create_index(op.f("ix_calendar_events_org_id"), "calendar_events", ["org_id"])
    for stmt in enable_rls_sql(SCHOOL_PLANNER_TABLES):
        op.execute(stmt)


def downgrade() -> None:
    for stmt in disable_rls_sql(SCHOOL_PLANNER_TABLES):
        op.execute(stmt)
    op.drop_table("calendar_events")
    op.drop_column("academic_years", "working_weekdays")
