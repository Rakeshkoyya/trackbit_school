"""bands: per-subject tiers, descriptors, promotion, owners and the weekly check-in (V1-9)

The module stops being a letter stamped on a child and becomes a **programme**:
assess against a written standard, group, give every C child an owner, work,
re-assess on evidence, and measure the **movement**.

- `band_descriptors` (`D-69`/`D-74`/`S-175`) — what a B child in English *can
  do*, per subject × tier, **shipped pre-written and editable**, carrying that
  subject's own threshold. Today the thresholds are two numbers for the whole
  school, so English and Maths are assumed to grade alike. `grade_group` is
  added now and left unused (`Q-76`): 9 texts get written, 72 do not, and the
  column is expensive to retrofit.
- `subjects.band_monitored` (`D-68`) — a flag, not a table. An unmonitored
  subject has no bands and no programme, and nothing else about it changes.
- `student_bands.subject_id` / `source` / `cycle_id` (`D-75`/`D-70`) — the band
  is **per subject** and a row explains itself. A child who reads two years
  below grade and is fine at arithmetic used to get one letter describing
  neither — and the daily check generator then handed him easier *maths*.
  Existing rows keep `subject_id NULL`: they are the **retired overall letter**,
  kept as history and read by nothing.
- `assessment_cycles.band_promoted_at/by` (`D-76`/`S-182`) — *"use this as the
  band test"* is a **flag, never a type change**: re-typing a slip test would
  delete it from the exam analytics, trading the test for the band.
- `interventions.subject_id` / `owner_member_id` / `exit_criterion` /
  `closed_at` / `outcome_note` (`D-77`/`S-167`/`S-180`) — one owner per (child ×
  subject), the exit criterion written when the child **enters**, and a status
  that can finally reach `achieved`. Until now nothing could close an
  intervention, so a goal met in July kept injecting a daily check in March.
- `support_checkpoints` (`D-87`/`S-165`) — the weekly check-in, append-only
  (law 3). **The only genuinely new capture in the module**: four fields, once a
  week, per child.

Revision ID: f8a9b0c1d2e3
Revises: e7f8a9b0c1d2
Create Date: 2026-08-02 22:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.rls import SCHOOL_BAND_TABLES, disable_rls_sql, enable_rls_sql

revision: str = "f8a9b0c1d2e3"
down_revision: str | None = "e7f8a9b0c1d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "band_descriptors",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("subject_id", sa.UUID(), nullable=False),
        sa.Column("tier", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        # The subject's own threshold (`D-74`). NULL on C — C is "below B",
        # never its own cut-off, or two thresholds could disagree.
        sa.Column("min_pct", sa.Integer(), nullable=True),
        # `Q-76`: added now, unused. Per-grade descriptors are 72 texts nobody
        # writes; the column costs nothing today and is expensive later.
        sa.Column("grade_group", sa.Text(), nullable=True),
        sa.CheckConstraint("tier IN ('A', 'B', 'C')",
                           name=op.f("ck_band_descriptors_tier_valid")),
        sa.CheckConstraint("min_pct IS NULL OR (min_pct >= 0 AND min_pct <= 100)",
                           name=op.f("ck_band_descriptors_min_pct_valid")),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"],
                                name=op.f("fk_band_descriptors_org_id_organizations"),
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"],
                                name=op.f("fk_band_descriptors_subject_id_subjects"),
                                ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_band_descriptors")),
        sa.UniqueConstraint("org_id", "subject_id", "tier", "grade_group",
                            name=op.f("uq_band_descriptors_subject_tier")),
    )
    op.create_index(op.f("ix_band_descriptors_org_id"), "band_descriptors", ["org_id"])

    op.create_table(
        "support_checkpoints",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("intervention_id", sa.UUID(), nullable=False),
        # The Monday of the week it belongs to — so "checked in this week" is a
        # lookup, not a date-range walk per child.
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("worked_on", sa.Text(), nullable=True),
        sa.Column("what_changed", sa.Text(), nullable=True),
        sa.Column("next_step", sa.Text(), nullable=True),
        sa.Column("ready_to_retest", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("author_member_id", sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"],
                                name=op.f("fk_support_checkpoints_org_id_organizations"),
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["intervention_id"], ["interventions.id"],
                                name=op.f("fk_support_checkpoints_intervention_id_interventions"),
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_member_id"], ["memberships.id"],
                                name=op.f("fk_support_checkpoints_author_member_id_memberships"),
                                ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_support_checkpoints")),
    )
    op.create_index(op.f("ix_support_checkpoints_org_id"), "support_checkpoints", ["org_id"])
    op.create_index(op.f("ix_support_checkpoints_intervention_id"), "support_checkpoints",
                    ["intervention_id"])

    op.add_column("subjects", sa.Column("band_monitored", sa.Boolean(),
                                        server_default=sa.text("false"), nullable=False))

    op.add_column("student_bands", sa.Column("subject_id", sa.UUID(), nullable=True))
    op.add_column("student_bands", sa.Column("source", sa.Text(),
                                             server_default="test", nullable=False))
    op.add_column("student_bands", sa.Column("cycle_id", sa.UUID(), nullable=True))
    op.create_check_constraint("source_valid", "student_bands",
                               "source IN ('test', 'observation')")
    op.create_foreign_key(op.f("fk_student_bands_subject_id_subjects"),
                          "student_bands", "subjects", ["subject_id"], ["id"],
                          ondelete="CASCADE")
    op.create_foreign_key(op.f("fk_student_bands_cycle_id_assessment_cycles"),
                          "student_bands", "assessment_cycles", ["cycle_id"], ["id"],
                          ondelete="SET NULL")
    op.create_index("ix_student_bands_student_subject", "student_bands",
                    ["student_id", "subject_id"])

    op.add_column("assessment_cycles",
                  sa.Column("band_promoted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("assessment_cycles", sa.Column("band_promoted_by", sa.UUID(), nullable=True))
    op.create_foreign_key(op.f("fk_assessment_cycles_band_promoted_by_memberships"),
                          "assessment_cycles", "memberships", ["band_promoted_by"], ["id"],
                          ondelete="SET NULL")

    op.add_column("interventions", sa.Column("subject_id", sa.UUID(), nullable=True))
    op.add_column("interventions", sa.Column("owner_member_id", sa.UUID(), nullable=True))
    op.add_column("interventions", sa.Column("exit_criterion", sa.Text(), nullable=True))
    op.add_column("interventions",
                  sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("interventions", sa.Column("outcome_note", sa.Text(), nullable=True))
    op.create_foreign_key(op.f("fk_interventions_subject_id_subjects"),
                          "interventions", "subjects", ["subject_id"], ["id"],
                          ondelete="CASCADE")
    op.create_foreign_key(op.f("fk_interventions_owner_member_id_memberships"),
                          "interventions", "memberships", ["owner_member_id"], ["id"],
                          ondelete="SET NULL")
    op.create_index("ix_interventions_owner", "interventions",
                    ["owner_member_id", "status"])

    for stmt in enable_rls_sql(SCHOOL_BAND_TABLES):
        op.execute(stmt)


def downgrade() -> None:
    for stmt in disable_rls_sql(SCHOOL_BAND_TABLES):
        op.execute(stmt)
    op.drop_index("ix_interventions_owner", table_name="interventions")
    op.drop_constraint(op.f("fk_interventions_owner_member_id_memberships"),
                       "interventions", type_="foreignkey")
    op.drop_constraint(op.f("fk_interventions_subject_id_subjects"),
                       "interventions", type_="foreignkey")
    for col in ("outcome_note", "closed_at", "exit_criterion", "owner_member_id", "subject_id"):
        op.drop_column("interventions", col)
    op.drop_constraint(op.f("fk_assessment_cycles_band_promoted_by_memberships"),
                       "assessment_cycles", type_="foreignkey")
    op.drop_column("assessment_cycles", "band_promoted_by")
    op.drop_column("assessment_cycles", "band_promoted_at")
    op.drop_index("ix_student_bands_student_subject", table_name="student_bands")
    op.drop_constraint(op.f("fk_student_bands_cycle_id_assessment_cycles"),
                       "student_bands", type_="foreignkey")
    op.drop_constraint(op.f("fk_student_bands_subject_id_subjects"),
                       "student_bands", type_="foreignkey")
    op.drop_constraint("ck_student_bands_source_valid", "student_bands", type_="check")
    for col in ("cycle_id", "source", "subject_id"):
        op.drop_column("student_bands", col)
    op.drop_column("subjects", "band_monitored")
    op.drop_table("support_checkpoints")
    op.drop_index(op.f("ix_band_descriptors_org_id"), table_name="band_descriptors")
    op.drop_table("band_descriptors")
