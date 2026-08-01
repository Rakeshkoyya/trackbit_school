"""per-student homework results + checking discipline (HW-1)

Founder decision 2026-07-29. Homework completion was a COUNT
(`homework_checks.done_count`), which cannot name a student — so "who keeps not
doing it", "which teacher never checks" and a parent's "did my child do
yesterday's homework" were all unanswerable.

- homework_results: exception rows, one per student who did NOT do it
  (not_done | partial). Capture-by-exception (P1v2) — every student's status is
  still derivable (roster minus these rows = done) without the teacher touching
  40 names to record 3 facts.
- homework_checks.checked_by_member_id: who actually checked. A substitute may
  check a colleague's homework, and the discipline report has to name a person.
- homework_checks gains UNIQUE(assignment_id): it was 1:1 only by service
  convention, so a double-submit could create a second row and double-count that
  class in the dashboard's homework totals.

done_count/total_count are KEPT and become derived caches, recomputed on every
check from roster minus results — so `DashboardService._homework_health` and the
existing homework chart keep working untouched.

Revision ID: d8e9f0a1b2c3
Revises: c7d8e9f0a1b2
Create Date: 2026-07-29 14:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.rls import SCHOOL_HOMEWORK_TABLES, disable_rls_sql, enable_rls_sql

revision: str = "d8e9f0a1b2c3"
down_revision: str | None = "c7d8e9f0a1b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "homework_checks",
        sa.Column("checked_by_member_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_homework_checks_checked_by_member_id_memberships"),
        "homework_checks", "memberships", ["checked_by_member_id"], ["id"], ondelete="SET NULL",
    )

    # Collapse any pre-existing duplicates before the unique index goes on, so the
    # migration cannot fail on real data. Keeps the most recently checked row.
    op.execute(
        """
        DELETE FROM homework_checks a
        USING homework_checks b
        WHERE a.assignment_id = b.assignment_id
          AND (
            COALESCE(a.checked_at, a.created_at) < COALESCE(b.checked_at, b.created_at)
            OR (COALESCE(a.checked_at, a.created_at) = COALESCE(b.checked_at, b.created_at)
                AND a.id < b.id)
          );
        """
    )
    op.create_unique_constraint(
        "uq_homework_checks_assignment", "homework_checks", ["assignment_id"])

    op.create_table(
        "homework_results",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("check_id", sa.UUID(), nullable=False),
        sa.Column("assignment_id", sa.UUID(), nullable=False),
        sa.Column("student_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.Text(), server_default="not_done", nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.CheckConstraint("status IN ('not_done', 'partial')",
                           name=op.f("ck_homework_results_homework_result_status_valid")),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"],
                                name=op.f("fk_homework_results_org_id_organizations"),
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["check_id"], ["homework_checks.id"],
                                name=op.f("fk_homework_results_check_id_homework_checks"),
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assignment_id"], ["homework_assignments.id"],
                                name=op.f(
                                    "fk_homework_results_assignment_id_homework_assignments"),
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"],
                                name=op.f("fk_homework_results_student_id_students"),
                                ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_homework_results")),
        sa.UniqueConstraint("assignment_id", "student_id", name="uq_homework_results_student"),
    )
    op.create_index(op.f("ix_homework_results_org_id"), "homework_results", ["org_id"])
    op.create_index(op.f("ix_homework_results_check_id"), "homework_results", ["check_id"])
    op.create_index(op.f("ix_homework_results_assignment_id"), "homework_results",
                    ["assignment_id"])
    op.create_index(op.f("ix_homework_results_student_id"), "homework_results", ["student_id"])

    for stmt in enable_rls_sql(SCHOOL_HOMEWORK_TABLES):
        op.execute(stmt)


def downgrade() -> None:
    for stmt in disable_rls_sql(SCHOOL_HOMEWORK_TABLES):
        op.execute(stmt)
    op.drop_table("homework_results")
    op.drop_constraint("uq_homework_checks_assignment", "homework_checks", type_="unique")
    op.drop_constraint(
        op.f("fk_homework_checks_checked_by_member_id_memberships"),
        "homework_checks", type_="foreignkey")
    op.drop_column("homework_checks", "checked_by_member_id")
