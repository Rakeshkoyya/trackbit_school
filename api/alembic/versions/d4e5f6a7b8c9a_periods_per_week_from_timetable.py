"""TT-3: backfill `periods_per_week` from the timetable it is now derived from.

Data only — no DDL. `class_subjects.periods_per_week` stopped being a number a
school types (the setup pack's Teaching Assignments sheet no longer asks for it)
and became a count of the live grid, maintained by
`services/period_load.py::recompute_periods_per_week`.

Existing rows still hold whatever was typed, which for most schools is 0 or
wrong — and it is the divisor the entire planner runs on, so until this runs
their chapters cannot be dated at all. This aligns them once; every later change
is maintained by the service.

**Classes with no timetable rows are left exactly as they are.** Same judgement
as the service (see its module docstring): there is nothing to derive from, and
zeroing would replace a half-set-up school's only figure with one that stops the
planner dead.

`downgrade` is a no-op on purpose. The previous values were free text a human
typed; they are not recoverable from anything in the schema, and inventing them
back would be worse than leaving the derived truth in place.

Revision ID: d4e5f6a7b8c9a
Revises: c3d4e5f6a7b8
"""

from alembic import op

revision: str = "d4e5f6a7b8c9a"
down_revision: str | None = "c3d4e5f6a7b8"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # One statement. The correlated count is the live subject slots for this
    # class-subject; the EXISTS restricts it to classes that actually have a
    # grid, so an untimetabled class keeps its typed value and a timetabled one
    # gets 0 for the subjects its grid never mentions.
    op.execute("""
        UPDATE class_subjects cs
           SET periods_per_week = (
                   SELECT count(*)
                     FROM timetable_slots ts
                    WHERE ts.class_subject_id = cs.id
                      AND ts.slot_type = 'subject'
                      AND ts.effective_to IS NULL)
         WHERE EXISTS (
                   SELECT 1
                     FROM timetable_slots ts2
                    WHERE ts2.class_id = cs.class_id
                      AND ts2.slot_type = 'subject'
                      AND ts2.effective_to IS NULL)
           AND cs.periods_per_week IS DISTINCT FROM (
                   SELECT count(*)
                     FROM timetable_slots ts3
                    WHERE ts3.class_subject_id = cs.id
                      AND ts3.slot_type = 'subject'
                      AND ts3.effective_to IS NULL)
    """)


def downgrade() -> None:
    """Nothing to undo — the old values were typed and are unrecoverable."""
