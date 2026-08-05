"""the support programme's own assessments (founder, 2026-08-05)

The ABC bands area gave a support owner two of the three things she needs: work
to give (per-student homework, reused rather than re-invented) and a weekly
check-in to write. The missing third is the one that closes the loop — **set a
check, and record how each child did on it** — without which "is he moving?" is
answered from memory.

Three tables, each shaped by a precedent already in this schema:

    band_assessments            the check she set. `metric` is the founder's
                                three — marks | rating | other — and the
                                arithmetic for each lives in
                                `core/band_assessment.py`, never re-derived.
    band_assessment_students    the explicit roster, only when it is not
                                everyone. `covers_all=true` means the roster is
                                COMPUTED (HS-1's `session_classes` rule), so a
                                child assigned to her next week is on it with
                                nobody remembering to edit anything.
    band_assessment_results     one row per child evaluated. **Its absence means
                                not evaluated** — never a zero, the
                                `homework_checks` rule again. Full replace on
                                save, like `homework_results` and
                                `attendance_exceptions`: results are capture, and
                                law 3's append-only is for decisions.

`student_notes` gains a nullable `assessment_id` and two kinds. The per-student
remark the evaluation sheet captures is the SAME log the class teacher writes —
one place a human observation about a child lives, with a pointer to what
occasioned it. A second per-assessment note table would put half the record
somewhere nobody scrolls.

Purely additive: three new tables, one nullable column, one widened CHECK. Code
that predates it is unaffected.

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-08-05 16:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.rls import (
    SCHOOL_BAND_ASSESSMENT_TABLES,
    disable_rls_sql,
    enable_rls_sql,
)

revision: str = "d3e4f5a6b7c8"
down_revision: str | None = "c2d3e4f5a6b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_KIND_OLD = ("general", "behaviour", "wellbeing", "achievement",
             "parent_contact", "concern")
_KIND_NEW = (*_KIND_OLD, "support", "assessment")


def _kind_check(values: tuple[str, ...]) -> str:
    return "kind IN (" + ", ".join(f"'{v}'" for v in values) + ")"


def upgrade() -> None:
    op.create_table(
        "band_assessments",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("class_id", sa.UUID(), nullable=False),
        # Nullable: a support owner is sometimes working on something that
        # crosses subjects ("sitting still for twenty minutes"), and refusing to
        # record that would push it into a notebook.
        sa.Column("subject_id", sa.UUID(), nullable=True),
        sa.Column("term_id", sa.UUID(), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        # Two fields, because they are read by two people at two moments: the
        # instruction the child is given, and the teacher's own note about why.
        sa.Column("instructions", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("metric", sa.Text(), server_default="marks", nullable=False),
        # Nullable rather than defaulted, so "she never said" stays
        # distinguishable from "out of 1".
        sa.Column("max_marks", sa.Numeric(6, 2), nullable=True),
        sa.Column("rating_max", sa.Integer(), nullable=True),
        sa.Column("covers_all", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("given_on", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("created_by_member_id", sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["class_id"], ["school_classes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["term_id"], ["terms.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_member_id"], ["memberships.id"],
                                ondelete="SET NULL"),
        sa.CheckConstraint("metric IN ('marks', 'rating', 'other')",
                           name="ck_band_assessments_metric"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_band_assessments_org_id", "band_assessments", ["org_id"])
    op.create_index("ix_band_assessments_class_id", "band_assessments", ["class_id"])
    # The one read the feed makes: this school's assessments, newest first.
    op.create_index("ix_band_assessments_org_given", "band_assessments",
                    ["org_id", sa.text("given_on DESC")])

    op.create_table(
        "band_assessment_students",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("assessment_id", sa.UUID(), nullable=False),
        sa.Column("student_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assessment_id"], ["band_assessments.id"],
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("assessment_id", "student_id",
                            name="uq_band_assessment_students"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_band_assessment_students_org_id",
                    "band_assessment_students", ["org_id"])
    op.create_index("ix_band_assessment_students_assessment_id",
                    "band_assessment_students", ["assessment_id"])
    op.create_index("ix_band_assessment_students_student_id",
                    "band_assessment_students", ["student_id"])

    op.create_table(
        "band_assessment_results",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("assessment_id", sa.UUID(), nullable=False),
        sa.Column("student_id", sa.UUID(), nullable=False),
        # One column per metric rather than a polymorphic `value`, so no query
        # can sum a rating with a mark by forgetting to check the metric.
        sa.Column("marks", sa.Numeric(6, 2), nullable=True),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.Column("verdict", sa.Text(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("recorded_by_member_id", sa.UUID(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assessment_id"], ["band_assessments.id"],
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recorded_by_member_id"], ["memberships.id"],
                                ondelete="SET NULL"),
        # One verdict per child per assessment. The full-replace save leans on
        # it, and without it a double-submit would double-count an average.
        sa.UniqueConstraint("assessment_id", "student_id",
                            name="uq_band_assessment_results"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_band_assessment_results_org_id",
                    "band_assessment_results", ["org_id"])
    op.create_index("ix_band_assessment_results_assessment_id",
                    "band_assessment_results", ["assessment_id"])
    op.create_index("ix_band_assessment_results_student_id",
                    "band_assessment_results", ["student_id"])

    # The student log gains a pointer to what occasioned it, and the two kinds
    # the programme writes.
    op.add_column("student_notes", sa.Column("assessment_id", sa.UUID(), nullable=True))
    op.create_foreign_key("fk_student_notes_assessment", "student_notes",
                          "band_assessments", ["assessment_id"], ["id"],
                          ondelete="SET NULL")
    op.create_index("ix_student_notes_assessment_id", "student_notes", ["assessment_id"])
    op.drop_constraint("ck_student_notes_kind", "student_notes", type_="check")
    op.create_check_constraint("ck_student_notes_kind", "student_notes",
                               _kind_check(_KIND_NEW))

    for stmt in enable_rls_sql(SCHOOL_BAND_ASSESSMENT_TABLES):
        op.execute(stmt)


def downgrade() -> None:
    for stmt in disable_rls_sql(SCHOOL_BAND_ASSESSMENT_TABLES):
        op.execute(stmt)

    # Rows written under the new kinds would fail the narrowed CHECK, so they
    # are folded back to the nearest kind that predates this migration rather
    # than blocking the downgrade.
    op.execute("UPDATE student_notes SET kind = 'general' "
               "WHERE kind IN ('support', 'assessment')")
    op.drop_constraint("ck_student_notes_kind", "student_notes", type_="check")
    op.create_check_constraint("ck_student_notes_kind", "student_notes",
                               _kind_check(_KIND_OLD))
    op.drop_index("ix_student_notes_assessment_id", table_name="student_notes")
    op.drop_constraint("fk_student_notes_assessment", "student_notes", type_="foreignkey")
    op.drop_column("student_notes", "assessment_id")

    op.drop_table("band_assessment_results")
    op.drop_table("band_assessment_students")
    op.drop_table("band_assessments")
