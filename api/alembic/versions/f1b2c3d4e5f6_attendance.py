"""attendance_marks + attendance_exceptions (V2-P2, SPRD2 §4.4/§5.4)

Revision ID: f1b2c3d4e5f6
Revises: f0a1b2c3d4e5
Create Date: 2026-07-08 11:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.rls import SCHOOL_ATTENDANCE_TABLES, disable_rls_sql, enable_rls_sql

revision: str = "f1b2c3d4e5f6"
down_revision: str | None = "f0a1b2c3d4e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "attendance_marks",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("class_id", sa.UUID(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("period_no", sa.Integer(), nullable=False),
        sa.Column("class_subject_id", sa.UUID(), nullable=True),
        sa.Column("marked_by_member_id", sa.UUID(), nullable=True),
        sa.Column("marked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("alerted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["class_id"], ["school_classes.id"], name=op.f("fk_attendance_marks_class_id_school_classes"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["class_subject_id"], ["class_subjects.id"], name=op.f("fk_attendance_marks_class_subject_id_class_subjects"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["marked_by_member_id"], ["memberships.id"], name=op.f("fk_attendance_marks_marked_by_member_id_memberships"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], name=op.f("fk_attendance_marks_org_id_organizations"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_attendance_marks")),
        sa.UniqueConstraint("class_id", "date", "period_no", name="uq_attendance_marks_class_period"),
        sa.CheckConstraint("period_no >= 1", name=op.f("ck_attendance_marks_period_no_valid")),
    )
    op.create_index(op.f("ix_attendance_marks_org_id"), "attendance_marks", ["org_id"])
    op.create_index(op.f("ix_attendance_marks_class_id"), "attendance_marks", ["class_id"])

    op.create_table(
        "attendance_exceptions",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("mark_id", sa.UUID(), nullable=False),
        sa.Column("student_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("late_minutes", sa.Integer(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.ForeignKeyConstraint(["mark_id"], ["attendance_marks.id"], name=op.f("fk_attendance_exceptions_mark_id_attendance_marks"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], name=op.f("fk_attendance_exceptions_org_id_organizations"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], name=op.f("fk_attendance_exceptions_student_id_students"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_attendance_exceptions")),
        sa.UniqueConstraint("mark_id", "student_id", name="uq_attendance_exceptions_mark_student"),
        sa.CheckConstraint("status IN ('absent', 'late')", name=op.f("ck_attendance_exceptions_status_valid")),
    )
    op.create_index(op.f("ix_attendance_exceptions_org_id"), "attendance_exceptions", ["org_id"])
    op.create_index(op.f("ix_attendance_exceptions_mark_id"), "attendance_exceptions", ["mark_id"])

    for stmt in enable_rls_sql(SCHOOL_ATTENDANCE_TABLES):
        op.execute(stmt)


def downgrade() -> None:
    for stmt in disable_rls_sql(SCHOOL_ATTENDANCE_TABLES):
        op.execute(stmt)
    op.drop_table("attendance_exceptions")
    op.drop_table("attendance_marks")
