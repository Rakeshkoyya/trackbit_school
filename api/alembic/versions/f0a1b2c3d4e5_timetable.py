"""timetable_slots + academic_years period timing (V2-P1, SPRD2 §4/§5.3)

Revision ID: f0a1b2c3d4e5
Revises: e9fab0c1d2e3
Create Date: 2026-07-07 16:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.core.rls import SCHOOL_TIMETABLE_TABLES, disable_rls_sql, enable_rls_sql

revision: str = "f0a1b2c3d4e5"
down_revision: str | None = "e9fab0c1d2e3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Period timing config on the academic year (school timings).
    op.add_column(
        "academic_years",
        sa.Column("periods_per_day", sa.Integer(), server_default="8", nullable=False),
    )
    op.add_column(
        "academic_years",
        sa.Column(
            "period_times",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )

    op.create_table(
        "timetable_slots",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("class_id", sa.UUID(), nullable=False),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("period_no", sa.Integer(), nullable=False),
        sa.Column("class_subject_id", sa.UUID(), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["class_id"], ["school_classes.id"], name=op.f("fk_timetable_slots_class_id_school_classes"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["class_subject_id"], ["class_subjects.id"], name=op.f("fk_timetable_slots_class_subject_id_class_subjects"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], name=op.f("fk_timetable_slots_org_id_organizations"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_timetable_slots")),
        sa.CheckConstraint("weekday >= 0 AND weekday <= 6", name=op.f("ck_timetable_slots_weekday_valid")),
        sa.CheckConstraint("period_no >= 1", name=op.f("ck_timetable_slots_period_no_valid")),
    )
    op.create_index(op.f("ix_timetable_slots_org_id"), "timetable_slots", ["org_id"])
    op.create_index(op.f("ix_timetable_slots_class_id"), "timetable_slots", ["class_id"])
    op.create_index(op.f("ix_timetable_slots_class_subject_id"), "timetable_slots", ["class_subject_id"])
    op.create_index("ix_timetable_slots_class_current", "timetable_slots", ["class_id", "effective_to"])

    for stmt in enable_rls_sql(SCHOOL_TIMETABLE_TABLES):
        op.execute(stmt)


def downgrade() -> None:
    for stmt in disable_rls_sql(SCHOOL_TIMETABLE_TABLES):
        op.execute(stmt)
    op.drop_table("timetable_slots")
    op.drop_column("academic_years", "period_times")
    op.drop_column("academic_years", "periods_per_day")
