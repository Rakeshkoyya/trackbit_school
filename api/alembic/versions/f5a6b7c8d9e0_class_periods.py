"""class_periods anchor: attendance_marks -> class_periods, lesson_logs.period_id (V2-P6)

Promotes `attendance_marks` — already one row per (class_id, date, period_no) — into
the period anchor every per-period capture hangs off, and gives `lesson_logs` a
`period_id` so a double period can record a different topic in each occurrence.

The table is RENAMED, not recreated: the OID is preserved, so its RLS policy,
grants and existing rows all carry over. `enable_rls_sql` is re-run on the new
name anyway (it is idempotent via DROP POLICY IF EXISTS).

Revision ID: f5a6b7c8d9e0
Revises: f4e5f6a7b8c9
Create Date: 2026-07-09 10:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.rls import disable_rls_sql, enable_rls_sql

revision: str = "f5a6b7c8d9e0"
down_revision: str | None = "f4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── attendance_marks -> class_periods ────────────────────────────────────
    op.rename_table("attendance_marks", "class_periods")
    op.execute("ALTER INDEX ix_attendance_marks_org_id RENAME TO ix_class_periods_org_id")
    op.execute("ALTER INDEX ix_attendance_marks_class_id RENAME TO ix_class_periods_class_id")
    op.execute("ALTER TABLE class_periods RENAME CONSTRAINT pk_attendance_marks TO pk_class_periods")
    op.execute(
        "ALTER TABLE class_periods RENAME CONSTRAINT uq_attendance_marks_class_period "
        "TO uq_class_periods_class_period")
    op.execute(
        "ALTER TABLE class_periods RENAME CONSTRAINT ck_attendance_marks_period_no_valid "
        "TO ck_class_periods_period_no_valid")

    # `marked_at` becomes nullable: a period is opened (row exists) before
    # attendance is submitted. Its not-null-ness is now the "marked" signal.
    op.alter_column("class_periods", "marked_at", new_column_name="attendance_marked_at",
                    existing_type=sa.DateTime(timezone=True), nullable=True)

    op.add_column("class_periods", sa.Column("teacher_member_id", sa.UUID(), nullable=True))
    op.add_column("class_periods", sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("class_periods", sa.Column("not_held_reason", sa.Text(), nullable=True))
    op.add_column("class_periods", sa.Column(
        "status", sa.Text(), nullable=False, server_default="held"))
    # Existing rows were created at mark time, so that timestamp is their open time.
    op.add_column("class_periods", sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE class_periods SET opened_at = COALESCE(attendance_marked_at, created_at)")
    op.alter_column("class_periods", "opened_at",
                    existing_type=sa.DateTime(timezone=True), nullable=False)
    # Backfill who took the period from whoever marked it.
    op.execute("UPDATE class_periods SET teacher_member_id = marked_by_member_id")

    op.create_foreign_key(
        op.f("fk_class_periods_teacher_member_id_memberships"), "class_periods", "memberships",
        ["teacher_member_id"], ["id"], ondelete="SET NULL")
    op.create_check_constraint(
        op.f("ck_class_periods_status_valid"), "class_periods", "status IN ('held', 'not_held')")

    # ── attendance_exceptions.mark_id -> period_id ───────────────────────────
    op.alter_column("attendance_exceptions", "mark_id", new_column_name="period_id",
                    existing_type=sa.UUID(), nullable=False)
    op.execute(
        "ALTER INDEX ix_attendance_exceptions_mark_id RENAME TO ix_attendance_exceptions_period_id")
    op.execute(
        "ALTER TABLE attendance_exceptions RENAME CONSTRAINT uq_attendance_exceptions_mark_student "
        "TO uq_attendance_exceptions_period_student")
    op.execute(
        "ALTER TABLE attendance_exceptions RENAME CONSTRAINT "
        "fk_attendance_exceptions_mark_id_attendance_marks "
        "TO fk_attendance_exceptions_period_id_class_periods")

    # ── lesson_logs.period_id ────────────────────────────────────────────────
    op.add_column("lesson_logs", sa.Column("period_id", sa.UUID(), nullable=True))
    op.create_index(op.f("ix_lesson_logs_period_id"), "lesson_logs", ["period_id"])
    op.create_foreign_key(
        op.f("fk_lesson_logs_period_id_class_periods"), "lesson_logs", "class_periods",
        ["period_id"], ["id"], ondelete="SET NULL")
    # Swap the day-scoped unique key for two partial ones so the period-scoped and
    # legacy regimes coexist without colliding.
    op.drop_constraint("uq_lesson_logs_class_subject_id", "lesson_logs", type_="unique")
    op.create_index("uq_lesson_logs_period_topic", "lesson_logs", ["period_id", "topic_id"],
                    unique=True, postgresql_where=sa.text("period_id IS NOT NULL"))
    op.create_index("uq_lesson_logs_cs_date_topic", "lesson_logs",
                    ["class_subject_id", "date", "topic_id"],
                    unique=True, postgresql_where=sa.text("period_id IS NULL"))

    for stmt in enable_rls_sql(("class_periods",)):
        op.execute(stmt)


def downgrade() -> None:
    for stmt in disable_rls_sql(("class_periods",)):
        op.execute(stmt)

    op.drop_index("uq_lesson_logs_cs_date_topic", table_name="lesson_logs")
    op.drop_index("uq_lesson_logs_period_topic", table_name="lesson_logs")
    op.create_unique_constraint("uq_lesson_logs_class_subject_id", "lesson_logs",
                                ["class_subject_id", "date", "topic_id"])
    op.drop_constraint(op.f("fk_lesson_logs_period_id_class_periods"), "lesson_logs",
                       type_="foreignkey")
    op.drop_index(op.f("ix_lesson_logs_period_id"), table_name="lesson_logs")
    op.drop_column("lesson_logs", "period_id")

    op.execute(
        "ALTER TABLE attendance_exceptions RENAME CONSTRAINT "
        "fk_attendance_exceptions_period_id_class_periods "
        "TO fk_attendance_exceptions_mark_id_attendance_marks")
    op.execute(
        "ALTER TABLE attendance_exceptions RENAME CONSTRAINT uq_attendance_exceptions_period_student "
        "TO uq_attendance_exceptions_mark_student")
    op.execute(
        "ALTER INDEX ix_attendance_exceptions_period_id RENAME TO ix_attendance_exceptions_mark_id")
    op.alter_column("attendance_exceptions", "period_id", new_column_name="mark_id",
                    existing_type=sa.UUID(), nullable=False)

    op.drop_constraint(op.f("ck_class_periods_status_valid"), "class_periods", type_="check")
    op.drop_constraint(op.f("fk_class_periods_teacher_member_id_memberships"), "class_periods",
                       type_="foreignkey")
    op.drop_column("class_periods", "opened_at")
    op.drop_column("class_periods", "status")
    op.drop_column("class_periods", "not_held_reason")
    op.drop_column("class_periods", "closed_at")
    op.drop_column("class_periods", "teacher_member_id")
    # Rows that never had attendance submitted cannot exist in the old shape.
    op.execute("DELETE FROM class_periods WHERE attendance_marked_at IS NULL")
    op.alter_column("class_periods", "attendance_marked_at", new_column_name="marked_at",
                    existing_type=sa.DateTime(timezone=True), nullable=False)

    op.execute("ALTER TABLE class_periods RENAME CONSTRAINT ck_class_periods_period_no_valid "
               "TO ck_attendance_marks_period_no_valid")
    op.execute("ALTER TABLE class_periods RENAME CONSTRAINT uq_class_periods_class_period "
               "TO uq_attendance_marks_class_period")
    op.execute("ALTER TABLE class_periods RENAME CONSTRAINT pk_class_periods TO pk_attendance_marks")
    op.execute("ALTER INDEX ix_class_periods_class_id RENAME TO ix_attendance_marks_class_id")
    op.execute("ALTER INDEX ix_class_periods_org_id RENAME TO ix_attendance_marks_org_id")
    op.rename_table("class_periods", "attendance_marks")

    for stmt in enable_rls_sql(("attendance_marks",)):
        op.execute(stmt)
