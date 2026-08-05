"""the syllabus board — chapter attributes, a frozen baseline, set-shaped exam portions
(founder, 2026-08-05)

Three changes, and the middle one is the reason the other two are safe to ship.

**1. The chapter gains the two columns the table has to have.** `difficulty` and
`remarks` are the school's own annotation of a chapter — the two facts a head of
department writes in the margin of a printed syllabus and which had nowhere to
live here. Plain editable columns, not an append-only log: law 3 governs
*decisions* (who approved the plan, who moved a child's band), and a remark is
an annotation corrected in place, the same call `homework_results` and
`attendance_exceptions` already make.

**2. `plan_entries.baseline_week_start` freezes the baseline at approval.**
`PlannerService._forecast_rows` computed `baseline_finish = max(week_start)` from
the LIVE rows, so the "baseline" was whatever the plan currently said. That was
harmless while the only writer was a full re-draft behind a lock — and it becomes
a hole the moment a teacher can move a chapter, because dragging chapters later
would raise `baseline_finish` to meet `projected_finish` and every red subject in
the school would turn green with nothing taught. Stamped once at `approve`, read
by the forecast as `COALESCE(baseline_week_start, week_start)`, never rewritten:
P2's "the approved plan is the baseline" becomes true of the *data* instead of
true only as long as nobody wrote to it.

**3. `exam_portion_units` makes a portion a SET of chapters.** `upto_topic_id` is
a prefix — "everything up to here" — which cannot express the thing schools
actually do: Term 1 examines chapters 1, 2, 3 and 5, and chapter 4 is held over
to Term 2. The prefix is kept and still read (`upto_topic_id` becomes nullable),
so every row written before today keeps its exact meaning and arithmetic; a
portion with explicit chapters uses them instead. One shape at read time, two
ways in.

Purely additive: two nullable columns, one nullable date, one new table, one
constraint relaxed. Code that predates it is unaffected.

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
Create Date: 2026-08-05 18:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.rls import (
    SCHOOL_SYLLABUS_TABLES,
    disable_rls_sql,
    enable_rls_sql,
)

revision: str = "e4f5a6b7c8d9"
down_revision: str | None = "d3e4f5a6b7c8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── 1. the chapter's own attributes ──────────────────────────────────────
    op.add_column("syllabus_units", sa.Column("difficulty", sa.Text(), nullable=True))
    op.add_column("syllabus_units", sa.Column("remarks", sa.Text(), nullable=True))
    # Nullable and unset by default: "nobody has judged this chapter yet" is the
    # honest starting state, and a defaulted 'moderate' would put a judgement
    # nobody made on every row of the board.
    op.create_check_constraint(
        "ck_syllabus_units_difficulty",
        "syllabus_units",
        "difficulty IS NULL OR difficulty IN ('easy', 'moderate', 'hard')",
    )

    # ── 2. the frozen baseline ───────────────────────────────────────────────
    op.add_column("plan_entries",
                  sa.Column("baseline_week_start", sa.Date(), nullable=True))
    # Backfill: every entry belonging to an already-approved plan is treated as
    # its own baseline, which is exactly what the forecast has been reading up to
    # now. Leaving it NULL would be identical in behaviour today (COALESCE) but
    # would let the FIRST reschedule move a baseline that was locked months ago.
    op.execute("""
        UPDATE plan_entries pe
           SET baseline_week_start = pe.week_start
          FROM plans p
         WHERE p.class_subject_id = pe.class_subject_id
           AND p.org_id = pe.org_id
           AND p.status IN ('approved', 'partial')
    """)

    # ── 3. the portion as a set of chapters ──────────────────────────────────
    op.alter_column("exam_portions", "upto_topic_id",
                    existing_type=sa.UUID(), nullable=True)
    op.create_table(
        "exam_portion_units",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"),
                  nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("portion_id", sa.UUID(), nullable=False),
        sa.Column("unit_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["portion_id"], ["exam_portions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["unit_id"], ["syllabus_units.id"], ondelete="CASCADE"),
        # A chapter is in the portion or it is not; saying it twice is the same
        # statement, and without this a double-submit would double its periods.
        sa.UniqueConstraint("portion_id", "unit_id", name="uq_exam_portion_units"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_exam_portion_units_org_id", "exam_portion_units", ["org_id"])
    op.create_index("ix_exam_portion_units_portion_id", "exam_portion_units",
                    ["portion_id"])
    op.create_index("ix_exam_portion_units_unit_id", "exam_portion_units", ["unit_id"])

    for stmt in enable_rls_sql(SCHOOL_SYLLABUS_TABLES):
        op.execute(stmt)


def downgrade() -> None:
    for stmt in disable_rls_sql(SCHOOL_SYLLABUS_TABLES):
        op.execute(stmt)
    op.drop_table("exam_portion_units")
    # A portion that only ever had explicit chapters has no prefix to fall back
    # to, so it cannot survive the column becoming NOT NULL again. Dropping the
    # row is the only honest option — it says nothing rather than saying the
    # wrong chapters.
    op.execute("DELETE FROM exam_portions WHERE upto_topic_id IS NULL")
    op.alter_column("exam_portions", "upto_topic_id",
                    existing_type=sa.UUID(), nullable=False)

    op.drop_column("plan_entries", "baseline_week_start")

    op.drop_constraint("ck_syllabus_units_difficulty", "syllabus_units", type_="check")
    op.drop_column("syllabus_units", "remarks")
    op.drop_column("syllabus_units", "difficulty")
