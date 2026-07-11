"""lesson observations — the optional deep log (teacher-view redesign)

One table, three shapes: a section row ("we did Vocabulary"), a concept row
("Vocabulary → Reading happened"), and per-student exception rows (only the
students a teacher tapped, rating needs_work/excellent). The whole-class default
stays implicit, exactly like attendance (P1v2) — there are never per-student
"fine" rows. Growth reads these as the topic-level signal under each chapter.

Revision ID: a8b9c0d1e2f3
Revises: f7c8d9e0f1a2
Create Date: 2026-07-11 09:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.rls import SCHOOL_OBSERVATION_TABLES, disable_rls_sql, enable_rls_sql

revision: str = "a8b9c0d1e2f3"
down_revision: str | None = "f7c8d9e0f1a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "lesson_observations",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("class_subject_id", sa.UUID(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("period_id", sa.UUID(), nullable=True),
        sa.Column("member_id", sa.UUID(), nullable=True),
        sa.Column("section", sa.Text(), nullable=False),
        sa.Column("concept", sa.Text(), nullable=True),
        sa.Column("student_id", sa.UUID(), nullable=True),
        sa.Column("rating", sa.Text(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
                  nullable=False),
        sa.CheckConstraint("rating IN ('excellent', 'needs_work')",
                           name=op.f("ck_lesson_observations_rating_valid")),
        sa.CheckConstraint("rating IS NULL OR student_id IS NOT NULL",
                           name=op.f("ck_lesson_observations_rating_needs_student")),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"],
                                name=op.f("fk_lesson_observations_org_id_organizations"),
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["class_subject_id"], ["class_subjects.id"],
            name=op.f("fk_lesson_observations_class_subject_id_class_subjects"),
            ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["period_id"], ["class_periods.id"],
                                name=op.f("fk_lesson_observations_period_id_class_periods"),
                                ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["member_id"], ["memberships.id"],
                                name=op.f("fk_lesson_observations_member_id_memberships"),
                                ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"],
                                name=op.f("fk_lesson_observations_student_id_students"),
                                ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lesson_observations")),
    )
    op.create_index(op.f("ix_lesson_observations_org_id"), "lesson_observations", ["org_id"])
    op.create_index(op.f("ix_lesson_observations_class_subject_id"), "lesson_observations",
                    ["class_subject_id"])
    op.create_index(op.f("ix_lesson_observations_period_id"), "lesson_observations", ["period_id"])
    op.create_index(op.f("ix_lesson_observations_student_id"), "lesson_observations",
                    ["student_id"])
    op.create_index("ix_lesson_observations_cs_date", "lesson_observations",
                    ["class_subject_id", "date"])

    for stmt in enable_rls_sql(SCHOOL_OBSERVATION_TABLES):
        op.execute(stmt)


def downgrade() -> None:
    for stmt in disable_rls_sql(SCHOOL_OBSERVATION_TABLES):
        op.execute(stmt)
    op.drop_table("lesson_observations")
