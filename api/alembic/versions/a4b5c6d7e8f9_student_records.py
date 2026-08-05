"""the student's two halves — an exam remark, and a class log that can name one child
(founder, 2026-08-05)

The Students area splits in two: **Directory**, the administration record a school
keeps about a child, and **Academics**, the record the school *makes* about them
day by day. Almost all of the second half already existed and was merely
unreachable — the exam feed, the growth report, the homework history, the
observations. Two things did not, and they are the whole of this migration.

**1. `assessment_scores.remark`.** When a teacher enters marks she is looking at
the paper, and that is the only moment she knows *why* the mark is what it is.
There was nowhere to put it, so the sentence was lost and the report card could
only ever say a number. Per (student, exam) rather than per student, because
"rushed the second half" is about one afternoon and stops being true by the next
test. Optional, always — a required remark is forty sentences typed to record
one, and P1v2 does not permit that.

**2. `lesson_observations.entry_kind` + the per-student index.** Nothing here is
a new capture surface. A class log entry is a `lesson_logs` row exactly as it has
been since P1, and a class-log line about ONE child is a `lesson_observations`
row exactly as it has been since the teacher-view redesign — the table was built
for "per-student exception rows hanging off a period's log" and already carries
`student_id`, `note` and an optional rating.

    ⚠️ The alternative was `lesson_logs.student_id`, mirroring
    `homework_assignments.student_id`, and it is the wrong call HERE. Fifteen
    call sites read `lesson_logs` as the record of what a CLASS was taught —
    `services/coverage.py`, `growth`, `daily_report`, `timeline`, the forecast,
    the capture heatmap. Every one of them would have to learn to exclude the
    per-student rows, and the first one that forgot would inflate the syllabus
    board with a lesson that reached one child. `lesson_observations` is read by
    none of them.

`entry_kind` separates the two things now living in that table: `observation`,
the tap-a-deviating-student flag written from the period card, and `log`, a line
a teacher deliberately wrote about one child on the class-log screen. They are
the same shape and are emphatically not the same act — the first is an exception
to a norm, the second is a note — and three readers proved it: `growth.py`
renders a rating-less row as `needs_work`, and `support.py` labelled one
**"excellent"**. Each read is now scoped to the kind it means.

Existing rows backfill to `observation`, which is what all of them are: nothing
but the period card has ever written to this table.

Purely additive: one nullable column, one default-backfilled text column, one
check constraint, one partial index. Code that predates it is unaffected.

Revision ID: a4b5c6d7e8f9
Revises: e4f5a6b7c8d9
Create Date: 2026-08-05 21:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a4b5c6d7e8f9"
down_revision: str | None = "e4f5a6b7c8d9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1 — the teacher's word about one paper.
    op.add_column("assessment_scores", sa.Column("remark", sa.Text(), nullable=True))

    # 2 — which act wrote this row. `server_default` backfills every existing row
    # to `observation`, which is what all of them are.
    op.add_column(
        "lesson_observations",
        sa.Column("entry_kind", sa.Text(), nullable=False, server_default="observation"),
    )
    op.create_check_constraint(
        "entry_kind_valid", "lesson_observations",
        "entry_kind IN ('observation', 'log')",
    )
    # The class-log screen reads one class-subject over a date range, which the
    # existing (class_subject, date) index already serves; this adds the read the
    # child's own log page makes.
    op.create_index(
        "ix_lesson_observations_student_date", "lesson_observations",
        ["student_id", "date"], postgresql_where=sa.text("student_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_lesson_observations_student_date", table_name="lesson_observations")
    op.drop_constraint("entry_kind_valid", "lesson_observations", type_="check")
    op.drop_column("lesson_observations", "entry_kind")
    op.drop_column("assessment_scores", "remark")
