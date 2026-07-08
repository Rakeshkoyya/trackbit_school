"""daily_checks + check_results + per-student homework (V2-P3, SPRD2 §4.4/§5.5)

Revision ID: f2c3d4e5f6a7
Revises: f1b2c3d4e5f6
Create Date: 2026-07-08 12:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.rls import SCHOOL_CHECKS_TABLES, disable_rls_sql, enable_rls_sql

revision: str = "f2c3d4e5f6a7"
down_revision: str | None = "f1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Per-student homework: nullable target on the class assignment.
    op.add_column(
        "homework_assignments",
        sa.Column("student_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_homework_assignments_student_id_students"),
        "homework_assignments", "students", ["student_id"], ["id"], ondelete="CASCADE",
    )

    op.create_table(
        "daily_checks",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("class_subject_id", sa.UUID(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), server_default="ai", nullable=False),
        sa.Column("band_scope", sa.Text(), server_default="all", nullable=False),
        sa.Column("student_id", sa.UUID(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_by", sa.UUID(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["class_subject_id"], ["class_subjects.id"], name=op.f("fk_daily_checks_class_subject_id_class_subjects"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["confirmed_by"], ["memberships.id"], name=op.f("fk_daily_checks_confirmed_by_memberships"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], name=op.f("fk_daily_checks_org_id_organizations"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], name=op.f("fk_daily_checks_student_id_students"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_daily_checks")),
        sa.CheckConstraint("source IN ('ai', 'teacher')", name=op.f("ck_daily_checks_source_valid")),
        sa.CheckConstraint("band_scope IN ('all', 'A', 'B', 'C')", name=op.f("ck_daily_checks_band_scope_valid")),
    )
    op.create_index(op.f("ix_daily_checks_org_id"), "daily_checks", ["org_id"])
    op.create_index(op.f("ix_daily_checks_class_subject_id"), "daily_checks", ["class_subject_id"])
    op.create_index("ix_daily_checks_cs_date", "daily_checks", ["class_subject_id", "date"])

    op.create_table(
        "check_results",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("check_id", sa.UUID(), nullable=False),
        sa.Column("student_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.ForeignKeyConstraint(["check_id"], ["daily_checks.id"], name=op.f("fk_check_results_check_id_daily_checks"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], name=op.f("fk_check_results_org_id_organizations"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], name=op.f("fk_check_results_student_id_students"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_check_results")),
        sa.UniqueConstraint("check_id", "student_id", name="uq_check_results_check_student"),
        sa.CheckConstraint("status IN ('not_done', 'note')", name=op.f("ck_check_results_status_valid")),
    )
    op.create_index(op.f("ix_check_results_org_id"), "check_results", ["org_id"])
    op.create_index(op.f("ix_check_results_check_id"), "check_results", ["check_id"])

    for stmt in enable_rls_sql(SCHOOL_CHECKS_TABLES):
        op.execute(stmt)


def downgrade() -> None:
    for stmt in disable_rls_sql(SCHOOL_CHECKS_TABLES):
        op.execute(stmt)
    op.drop_table("check_results")
    op.drop_table("daily_checks")
    op.drop_constraint(op.f("fk_homework_assignments_student_id_students"), "homework_assignments", type_="foreignkey")
    op.drop_column("homework_assignments", "student_id")
