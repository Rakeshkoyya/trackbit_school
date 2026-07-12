"""exam capture + band config (SC-5)

The scores screen becomes exam-first: an exam is a class-scoped cycle carrying
its own paper metadata, and the photo capture can start BEFORE the cycle exists
(drop the papers, let the parse propose title/subject/total, create the cycle on
the human's save).

- `assessment_cycles` gains `topic`, `total_marks` (the paper's out-of),
  `student_ids` (JSONB subset for a few-students test; NULL = whole class) and
  `created_by_member_id`; the type check widens to the tests schools actually
  run (chapter/class/slip test, objective, band_test for categorization).
- `score_captures.cycle_id` becomes nullable (a draft exam capture — the cycle
  is created when the review is saved); `parsed_meta` holds the AI-read exam
  header, `student_ids` mirrors the subset. The one-target check relaxes to
  at-most-one because a draft's subject is unknown until the parse.
- `organizations` gains the band categorization thresholds (band_a_min /
  band_b_min, percentages) — admin-configurable on the Bands screen.

Revision ID: fb2c3d4e5f6a
Revises: fae1f2a3b4c5
Create Date: 2026-07-12 09:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "fb2c3d4e5f6a"
down_revision: str | None = "fae1f2a3b4c5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TYPES = ("diagnostic", "unit_test", "term_exam", "daily_test",
          "chapter_test", "class_test", "slip_test", "objective", "band_test")


def upgrade() -> None:
    # ── cycles: exam metadata ────────────────────────────────────────────────
    op.add_column("assessment_cycles", sa.Column("topic", sa.Text(), nullable=True))
    op.add_column("assessment_cycles",
                  sa.Column("total_marks", sa.Numeric(6, 2), nullable=True))
    op.add_column("assessment_cycles", sa.Column("student_ids", JSONB(), nullable=True))
    op.add_column("assessment_cycles",
                  sa.Column("created_by_member_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        op.f("fk_assessment_cycles_created_by_member_id_memberships"),
        "assessment_cycles", "memberships", ["created_by_member_id"], ["id"],
        ondelete="SET NULL")
    op.drop_constraint("type_valid", "assessment_cycles", type_="check")
    op.create_check_constraint(
        "type_valid", "assessment_cycles",
        "type IN ({})".format(", ".join(f"'{t}'" for t in _TYPES)))

    # ── captures: draft-first (cycle created on save) ────────────────────────
    op.alter_column("score_captures", "cycle_id", nullable=True,
                    existing_type=sa.UUID())
    op.add_column("score_captures", sa.Column("parsed_meta", JSONB(), nullable=True))
    op.add_column("score_captures", sa.Column("student_ids", JSONB(), nullable=True))
    op.drop_constraint("capture_one_target", "score_captures", type_="check")
    op.create_check_constraint(
        "capture_one_target", "score_captures",
        "num_nonnulls(subject_id, skill_area_id) <= 1")

    # ── org band thresholds ──────────────────────────────────────────────────
    op.add_column("organizations", sa.Column(
        "band_a_min", sa.Integer(), server_default="75", nullable=False))
    op.add_column("organizations", sa.Column(
        "band_b_min", sa.Integer(), server_default="50", nullable=False))
    op.create_check_constraint(
        "band_thresholds_valid", "organizations",
        "band_b_min > 0 AND band_b_min < band_a_min AND band_a_min <= 100")


def downgrade() -> None:
    op.drop_constraint("band_thresholds_valid", "organizations", type_="check")
    op.drop_column("organizations", "band_b_min")
    op.drop_column("organizations", "band_a_min")

    op.drop_constraint("capture_one_target", "score_captures", type_="check")
    op.create_check_constraint(
        "capture_one_target", "score_captures",
        "num_nonnulls(subject_id, skill_area_id) = 1")
    op.drop_column("score_captures", "student_ids")
    op.drop_column("score_captures", "parsed_meta")
    op.execute("DELETE FROM score_captures WHERE cycle_id IS NULL")
    op.alter_column("score_captures", "cycle_id", nullable=False,
                    existing_type=sa.UUID())

    op.drop_constraint("type_valid", "assessment_cycles", type_="check")
    op.execute("DELETE FROM assessment_cycles WHERE type NOT IN "
               "('diagnostic', 'unit_test', 'term_exam', 'daily_test')")
    op.create_check_constraint(
        "type_valid", "assessment_cycles",
        "type IN ('diagnostic', 'unit_test', 'term_exam', 'daily_test')")
    op.drop_constraint(
        op.f("fk_assessment_cycles_created_by_member_id_memberships"),
        "assessment_cycles", type_="foreignkey")
    op.drop_column("assessment_cycles", "created_by_member_id")
    op.drop_column("assessment_cycles", "student_ids")
    op.drop_column("assessment_cycles", "total_marks")
    op.drop_column("assessment_cycles", "topic")
