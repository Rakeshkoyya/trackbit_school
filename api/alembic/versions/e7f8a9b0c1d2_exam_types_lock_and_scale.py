"""exams: the school's own type, the lock, the scale and the per-student script (V1-8)

Six changes, and every one of them exists because a number on a screen is
currently untrue or unsavable.

- `exam_types` — the school's own word (`D-55`/`S-135`). A school running **CET**
  could not record one: `assessment_cycles.type` is a CHECK over nine values, so
  CET was filed as `class_test` and no analytic could ever separate it again.
  A table rather than free text because the exam type is the grouping key for a
  year of trend lines, and "CET" / "C.E.T" / "Cet" typed on three evenings become
  three series on a chart.
- `assessment_cycles.scale` — `minor` | `major`, never pooled (`S-114`, `Q-50`).
  Today a 5-mark slip test and an 80-mark term exam are added into one fraction
  on three screens at once.
- `exam_lock_events` + `locked_at`/`locked_by` — verify-and-lock (`D-53`), the
  append-only shape (`Q-62`, law 3) with the columns as a derived cache. This is
  what stops `ExamService.save`'s full delete-and-reinsert silently replacing
  July's confirmed mark in November.
- `assessment_cycles.exam_event_id` — the nullable FK to the planned exam block
  (`S-115`), which is the join `exam_portions` was built for.
- `assessment_scores.question_marks` — the per-question marks read off the marked
  script (§4's reconciliation: no new table, no new capture surface).
- `score_captures.mode` / `locked_rows` / `corrections` and
  `score_capture_pages.student_id` — the per-student script flow (`D-80`/`D-82`)
  and the training pair written once at lock (`D-54`/`S-137`), plus
  `organizations.training_data_opt_in`, default off and asked for (`S-138`).

Backfill: existing cycles get their `scale` from their system kind, and each org
gets one `exam_types` row per kind it has actually used, linked back — so the
"school's word" rendering works from the first load rather than after somebody
opens Setup.

Revision ID: e7f8a9b0c1d2
Revises: d6e7f8a9b0c1
Create Date: 2026-08-02 20:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.rls import SCHOOL_EXAM_TYPE_TABLES, disable_rls_sql, enable_rls_sql

revision: str = "e7f8a9b0c1d2"
down_revision: str | None = "d6e7f8a9b0c1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (system kind, the label a school sees before it renames it, scale, position).
# Mirrors `core/exams.py::SYSTEM_TYPES` — that module is the source of truth for
# code; this literal exists because a migration must not import behaviour that
# may change under it.
_SEED_TYPES = (
    ("slip_test", "Slip test", "minor", 10),
    ("class_test", "Class test", "minor", 20),
    ("chapter_test", "Chapter test", "minor", 30),
    ("daily_test", "Daily test", "minor", 40),
    ("objective", "Objective test", "minor", 50),
    ("band_test", "Band test", "minor", 60),
    ("diagnostic", "Diagnostic", "minor", 70),
    ("unit_test", "Unit test", "major", 80),
    ("term_exam", "Term exam", "major", 90),
)


def upgrade() -> None:
    op.create_table(
        "exam_types",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("system_type", sa.Text(), nullable=False),
        sa.Column("scale", sa.Text(), server_default="minor", nullable=False),
        sa.Column("position", sa.Integer(), server_default="0", nullable=False),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=False),
        sa.CheckConstraint("scale IN ('minor', 'major')",
                           name=op.f("ck_exam_types_exam_type_scale_valid")),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"],
                                name=op.f("fk_exam_types_org_id_organizations"),
                                ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_exam_types")),
        sa.UniqueConstraint("org_id", "name", name=op.f("uq_exam_types_org_name")),
    )
    op.create_index(op.f("ix_exam_types_org_id"), "exam_types", ["org_id"])

    op.create_table(
        "exam_lock_events",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("cycle_id", sa.UUID(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("actor_member_id", sa.UUID(), nullable=True),
        sa.CheckConstraint("action IN ('lock', 'unlock')",
                           name=op.f("ck_exam_lock_events_lock_action_valid")),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"],
                                name=op.f("fk_exam_lock_events_org_id_organizations"),
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cycle_id"], ["assessment_cycles.id"],
                                name=op.f("fk_exam_lock_events_cycle_id_assessment_cycles"),
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_member_id"], ["memberships.id"],
                                name=op.f("fk_exam_lock_events_actor_member_id_memberships"),
                                ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_exam_lock_events")),
    )
    op.create_index(op.f("ix_exam_lock_events_org_id"), "exam_lock_events", ["org_id"])
    op.create_index(op.f("ix_exam_lock_events_cycle_id"), "exam_lock_events", ["cycle_id"])

    op.add_column("assessment_cycles", sa.Column("exam_type_id", sa.UUID(), nullable=True))
    op.add_column("assessment_cycles",
                  sa.Column("scale", sa.Text(), server_default="minor", nullable=False))
    op.add_column("assessment_cycles", sa.Column("exam_event_id", sa.UUID(), nullable=True))
    op.add_column("assessment_cycles",
                  sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("assessment_cycles", sa.Column("locked_by", sa.UUID(), nullable=True))
    op.create_check_constraint("scale_valid", "assessment_cycles",
                               "scale IN ('minor', 'major')")
    op.create_foreign_key(op.f("fk_assessment_cycles_exam_type_id_exam_types"),
                          "assessment_cycles", "exam_types", ["exam_type_id"], ["id"],
                          ondelete="SET NULL")
    op.create_foreign_key(op.f("fk_assessment_cycles_exam_event_id_calendar_events"),
                          "assessment_cycles", "calendar_events", ["exam_event_id"], ["id"],
                          ondelete="SET NULL")
    op.create_foreign_key(op.f("fk_assessment_cycles_locked_by_users"),
                          "assessment_cycles", "users", ["locked_by"], ["id"],
                          ondelete="SET NULL")

    op.add_column("assessment_scores",
                  sa.Column("question_marks", sa.dialects.postgresql.JSONB(), nullable=True))

    op.add_column("score_captures",
                  sa.Column("mode", sa.Text(), server_default="register", nullable=False))
    op.create_check_constraint("capture_mode_valid", "score_captures",
                               "mode IN ('register', 'scripts')")
    op.add_column("score_captures",
                  sa.Column("locked_rows", sa.dialects.postgresql.JSONB(), nullable=True))
    op.add_column("score_captures",
                  sa.Column("corrections", sa.dialects.postgresql.JSONB(), nullable=True))

    op.add_column("score_capture_pages", sa.Column("student_id", sa.UUID(), nullable=True))
    op.create_index(op.f("ix_score_capture_pages_student_id"), "score_capture_pages",
                    ["student_id"])
    op.create_foreign_key(op.f("fk_score_capture_pages_student_id_students"),
                          "score_capture_pages", "students", ["student_id"], ["id"],
                          ondelete="SET NULL")

    op.add_column("organizations",
                  sa.Column("training_data_opt_in", sa.Boolean(),
                            server_default=sa.text("false"), nullable=False))

    # ── backfill ─────────────────────────────────────────────────────────────
    # One exam type per (org, kind actually used), named as the school will first
    # see it, then every existing cycle linked and given its scale. An org with
    # no exams gets no rows — the seeder in `ExamTypeService.ensure_defaults`
    # fills those in on first use, so nobody inherits nine unused words.
    values = ", ".join(
        f"('{t}', '{label}', '{scale}', {pos})" for t, label, scale, pos in _SEED_TYPES)
    op.execute(f"""
        INSERT INTO exam_types (org_id, name, system_type, scale, position, active)
        SELECT DISTINCT c.org_id, s.label, s.t, s.scale, s.pos, true
          FROM assessment_cycles c
          JOIN (VALUES {values}) AS s(t, label, scale, pos) ON s.t = c.type
        ON CONFLICT (org_id, name) DO NOTHING
    """)
    op.execute("""
        UPDATE assessment_cycles c
           SET exam_type_id = et.id, scale = et.scale
          FROM exam_types et
         WHERE et.org_id = c.org_id AND et.system_type = c.type
           AND c.exam_type_id IS NULL
    """)

    # Law 2: both new tables are org-scoped and get the org_isolation policy.
    for stmt in enable_rls_sql(SCHOOL_EXAM_TYPE_TABLES):
        op.execute(stmt)


def downgrade() -> None:
    for stmt in disable_rls_sql(SCHOOL_EXAM_TYPE_TABLES):
        op.execute(stmt)
    op.drop_column("organizations", "training_data_opt_in")
    op.drop_constraint(op.f("fk_score_capture_pages_student_id_students"),
                       "score_capture_pages", type_="foreignkey")
    op.drop_index(op.f("ix_score_capture_pages_student_id"), table_name="score_capture_pages")
    op.drop_column("score_capture_pages", "student_id")
    op.drop_column("score_captures", "corrections")
    op.drop_column("score_captures", "locked_rows")
    op.drop_constraint("ck_score_captures_capture_mode_valid", "score_captures",
                       type_="check")
    op.drop_column("score_captures", "mode")
    op.drop_column("assessment_scores", "question_marks")
    op.drop_constraint(op.f("fk_assessment_cycles_locked_by_users"),
                       "assessment_cycles", type_="foreignkey")
    op.drop_constraint(op.f("fk_assessment_cycles_exam_event_id_calendar_events"),
                       "assessment_cycles", type_="foreignkey")
    op.drop_constraint(op.f("fk_assessment_cycles_exam_type_id_exam_types"),
                       "assessment_cycles", type_="foreignkey")
    op.drop_constraint("ck_assessment_cycles_scale_valid", "assessment_cycles", type_="check")
    op.drop_column("assessment_cycles", "locked_by")
    op.drop_column("assessment_cycles", "locked_at")
    op.drop_column("assessment_cycles", "exam_event_id")
    op.drop_column("assessment_cycles", "scale")
    op.drop_column("assessment_cycles", "exam_type_id")
    op.drop_table("exam_lock_events")
    op.drop_index(op.f("ix_exam_types_org_id"), table_name="exam_types")
    op.drop_table("exam_types")
