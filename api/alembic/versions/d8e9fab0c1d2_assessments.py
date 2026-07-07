"""assessments & bands: skill_areas/cycles/scores/bands/interventions (SPRD §4.5, M3)

Revision ID: d8e9fab0c1d2
Revises: d7d8e9fab0c1
Create Date: 2026-07-07 15:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.rls import SCHOOL_ASSESSMENT_TABLES, disable_rls_sql, enable_rls_sql

revision: str = "d8e9fab0c1d2"
down_revision: str | None = "d7d8e9fab0c1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SCORE = sa.Numeric(6, 2)


def upgrade() -> None:
    op.create_table(
        "skill_areas",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), server_default="0", nullable=False),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], name=op.f("fk_skill_areas_org_id_organizations"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_skill_areas")),
        sa.UniqueConstraint("org_id", "name", name=op.f("uq_skill_areas_org_id")),
    )
    op.create_index(op.f("ix_skill_areas_org_id"), "skill_areas", ["org_id"])

    op.create_table(
        "assessment_cycles",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("term_id", sa.UUID(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("type IN ('diagnostic', 'unit_test', 'term_exam')", name=op.f("ck_assessment_cycles_type_valid")),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], name=op.f("fk_assessment_cycles_org_id_organizations"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["term_id"], ["terms.id"], name=op.f("fk_assessment_cycles_term_id_terms"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assessment_cycles")),
    )
    op.create_index(op.f("ix_assessment_cycles_org_id"), "assessment_cycles", ["org_id"])

    op.create_table(
        "assessment_scores",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("cycle_id", sa.UUID(), nullable=False),
        sa.Column("student_id", sa.UUID(), nullable=False),
        sa.Column("subject_id", sa.UUID(), nullable=True),
        sa.Column("skill_area_id", sa.UUID(), nullable=True),
        sa.Column("score", _SCORE, nullable=False),
        sa.Column("max_score", _SCORE, server_default="100", nullable=False),
        sa.Column("entered_by", sa.UUID(), nullable=True),
        sa.Column("verified_by", sa.UUID(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("num_nonnulls(subject_id, skill_area_id) = 1", name=op.f("ck_assessment_scores_one_target")),
        sa.ForeignKeyConstraint(["cycle_id"], ["assessment_cycles.id"], name=op.f("fk_assessment_scores_cycle_id_assessment_cycles"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["entered_by"], ["users.id"], name=op.f("fk_assessment_scores_entered_by_users"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], name=op.f("fk_assessment_scores_org_id_organizations"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["skill_area_id"], ["skill_areas.id"], name=op.f("fk_assessment_scores_skill_area_id_skill_areas"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], name=op.f("fk_assessment_scores_student_id_students"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], name=op.f("fk_assessment_scores_subject_id_subjects"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["verified_by"], ["users.id"], name=op.f("fk_assessment_scores_verified_by_users"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assessment_scores")),
    )
    op.create_index(op.f("ix_assessment_scores_cycle_id"), "assessment_scores", ["cycle_id"])
    op.create_index(op.f("ix_assessment_scores_org_id"), "assessment_scores", ["org_id"])

    op.create_table(
        "student_bands",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("student_id", sa.UUID(), nullable=False),
        sa.Column("term_id", sa.UUID(), nullable=False),
        sa.Column("tier", sa.Text(), nullable=False),
        sa.Column("scope_skill_area_id", sa.UUID(), nullable=True),
        sa.Column("set_by", sa.UUID(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("tier IN ('A', 'B', 'C')", name=op.f("ck_student_bands_tier_valid")),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], name=op.f("fk_student_bands_org_id_organizations"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["scope_skill_area_id"], ["skill_areas.id"], name=op.f("fk_student_bands_scope_skill_area_id_skill_areas"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["set_by"], ["users.id"], name=op.f("fk_student_bands_set_by_users"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], name=op.f("fk_student_bands_student_id_students"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["term_id"], ["terms.id"], name=op.f("fk_student_bands_term_id_terms"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_student_bands")),
    )
    op.create_index(op.f("ix_student_bands_org_id"), "student_bands", ["org_id"])
    op.create_index(op.f("ix_student_bands_student_id"), "student_bands", ["student_id"])

    op.create_table(
        "interventions",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("student_id", sa.UUID(), nullable=False),
        sa.Column("term_id", sa.UUID(), nullable=False),
        sa.Column("goal_text", sa.Text(), nullable=False),
        sa.Column("target_tier", sa.Text(), server_default="B", nullable=False),
        sa.Column("status", sa.Text(), server_default="active", nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status IN ('active', 'achieved', 'dropped')", name=op.f("ck_interventions_status_valid")),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], name=op.f("fk_interventions_org_id_organizations"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], name=op.f("fk_interventions_student_id_students"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["term_id"], ["terms.id"], name=op.f("fk_interventions_term_id_terms"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_interventions")),
    )
    op.create_index(op.f("ix_interventions_org_id"), "interventions", ["org_id"])
    op.create_index(op.f("ix_interventions_student_id"), "interventions", ["student_id"])

    op.create_table(
        "intervention_items",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("intervention_id", sa.UUID(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("task_instance_id", sa.UUID(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["intervention_id"], ["interventions.id"], name=op.f("fk_intervention_items_intervention_id_interventions"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], name=op.f("fk_intervention_items_org_id_organizations"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_instance_id"], ["task_instances.id"], name=op.f("fk_intervention_items_task_instance_id_task_instances"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_intervention_items")),
    )
    op.create_index(op.f("ix_intervention_items_intervention_id"), "intervention_items", ["intervention_id"])
    op.create_index(op.f("ix_intervention_items_org_id"), "intervention_items", ["org_id"])

    for stmt in enable_rls_sql(SCHOOL_ASSESSMENT_TABLES):
        op.execute(stmt)


def downgrade() -> None:
    for stmt in disable_rls_sql(SCHOOL_ASSESSMENT_TABLES):
        op.execute(stmt)
    for table in ("intervention_items", "interventions", "student_bands",
                  "assessment_scores", "assessment_cycles", "skill_areas"):
        op.drop_table(table)
