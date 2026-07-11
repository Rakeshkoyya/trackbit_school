"""photo score capture (SC-1)

Teachers photograph evaluated papers / a mark register instead of typing scores.

`assessment_cycles` gains `daily_test` (a class × subject × date cycle) plus
nullable `class_id` + `subject_id` — NULL on both keeps existing org-wide cycles
(diagnostics, term exams) exactly as they were.

Two new tables:
- `score_captures` — the draft container for one (cycle × class × subject-or-skill)
  photo batch. The AI transcription + deterministic roster match live in
  `parsed_rows` (JSONB); `assessment_scores` are written only when a human
  confirms the review grid (§8). Statuses: uploaded → parsed → confirmed, or
  discarded.
- `score_capture_pages` — the photographed pages as R2 object keys, kept forever
  as evidence (P5).

Revision ID: fae1f2a3b4c5
Revises: f9e0f1a2b3c4
Create Date: 2026-07-12 10:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

from app.core.rls import SCHOOL_CAPTURE_TABLES, disable_rls_sql, enable_rls_sql

revision: str = "fae1f2a3b4c5"
down_revision: str | None = "f9e0f1a2b3c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── cycles: daily_test + class/subject scoping ───────────────────────────
    op.add_column("assessment_cycles", sa.Column("class_id", sa.UUID(), nullable=True))
    op.add_column("assessment_cycles", sa.Column("subject_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        op.f("fk_assessment_cycles_class_id_school_classes"), "assessment_cycles",
        "school_classes", ["class_id"], ["id"], ondelete="CASCADE")
    op.create_foreign_key(
        op.f("fk_assessment_cycles_subject_id_subjects"), "assessment_cycles",
        "subjects", ["subject_id"], ["id"], ondelete="CASCADE")
    op.drop_constraint("type_valid", "assessment_cycles", type_="check")
    op.create_check_constraint(
        "type_valid", "assessment_cycles",
        "type IN ('diagnostic', 'unit_test', 'term_exam', 'daily_test')")

    # ── score_captures ───────────────────────────────────────────────────────
    op.create_table(
        "score_captures",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("cycle_id", sa.UUID(), nullable=False),
        sa.Column("class_id", sa.UUID(), nullable=False),
        sa.Column("subject_id", sa.UUID(), nullable=True),
        sa.Column("skill_area_id", sa.UUID(), nullable=True),
        sa.Column("status", sa.Text(), server_default="uploaded", nullable=False),
        sa.Column("parsed_rows", JSONB(), nullable=True),
        sa.Column("parse_error", sa.Text(), nullable=True),
        sa.Column("created_by_member_id", sa.UUID(), nullable=True),
        sa.Column("confirmed_by_member_id", sa.UUID(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
                  nullable=False),
        sa.CheckConstraint("num_nonnulls(subject_id, skill_area_id) = 1",
                           name=op.f("ck_score_captures_capture_one_target")),
        sa.CheckConstraint("status IN ('uploaded', 'parsed', 'confirmed', 'discarded')",
                           name=op.f("ck_score_captures_status_valid")),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"],
                                name=op.f("fk_score_captures_org_id_organizations"),
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cycle_id"], ["assessment_cycles.id"],
                                name=op.f("fk_score_captures_cycle_id_assessment_cycles"),
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["class_id"], ["school_classes.id"],
                                name=op.f("fk_score_captures_class_id_school_classes"),
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"],
                                name=op.f("fk_score_captures_subject_id_subjects"),
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["skill_area_id"], ["skill_areas.id"],
                                name=op.f("fk_score_captures_skill_area_id_skill_areas"),
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_member_id"], ["memberships.id"],
                                name=op.f("fk_score_captures_created_by_member_id_memberships"),
                                ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["confirmed_by_member_id"], ["memberships.id"],
                                name=op.f("fk_score_captures_confirmed_by_member_id_memberships"),
                                ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_score_captures")),
    )
    op.create_index(op.f("ix_score_captures_org_id"), "score_captures", ["org_id"])
    op.create_index(op.f("ix_score_captures_cycle_id"), "score_captures", ["cycle_id"])

    # ── score_capture_pages ──────────────────────────────────────────────────
    op.create_table(
        "score_capture_pages",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("capture_id", sa.UUID(), nullable=False),
        sa.Column("page_no", sa.Integer(), nullable=False),
        sa.Column("object_key", sa.Text(), nullable=False),
        sa.Column("content_type", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
                  nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"],
                                name=op.f("fk_score_capture_pages_org_id_organizations"),
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["capture_id"], ["score_captures.id"],
                                name=op.f("fk_score_capture_pages_capture_id_score_captures"),
                                ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_score_capture_pages")),
        sa.UniqueConstraint("capture_id", "page_no",
                            name=op.f("uq_score_capture_pages_capture_id")),
    )
    op.create_index(op.f("ix_score_capture_pages_org_id"), "score_capture_pages", ["org_id"])
    op.create_index(op.f("ix_score_capture_pages_capture_id"), "score_capture_pages",
                    ["capture_id"])

    for stmt in enable_rls_sql(SCHOOL_CAPTURE_TABLES):
        op.execute(stmt)


def downgrade() -> None:
    for stmt in disable_rls_sql(SCHOOL_CAPTURE_TABLES):
        op.execute(stmt)
    op.drop_table("score_capture_pages")
    op.drop_table("score_captures")

    op.execute("DELETE FROM assessment_cycles WHERE type = 'daily_test'")
    op.drop_constraint("type_valid", "assessment_cycles", type_="check")
    op.create_check_constraint(
        "type_valid", "assessment_cycles",
        "type IN ('diagnostic', 'unit_test', 'term_exam')")
    op.drop_constraint(op.f("fk_assessment_cycles_subject_id_subjects"),
                       "assessment_cycles", type_="foreignkey")
    op.drop_constraint(op.f("fk_assessment_cycles_class_id_school_classes"),
                       "assessment_cycles", type_="foreignkey")
    op.drop_column("assessment_cycles", "subject_id")
    op.drop_column("assessment_cycles", "class_id")
