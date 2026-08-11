"""One register a day is the default attendance mode (founder, 2026-08-11).

`organizations.attendance_mode` has defaulted to `every_period` since V1-2. That
is the rarest of the three shapes and the most expensive one: it asks a teacher
for the register in every timetabled period, which is exactly the per-class,
per-period chore the one-minute budget (P1v2) exists to prevent. Almost every
school takes ONE roll call a day.

So the column default becomes `first_period`, and — because the column is NOT
NULL and has always carried a value — **existing orgs still sitting on the old
default are moved with it**. A stored `every_period` cannot be told apart from an
inherited one: the column has never been nullable, so there is no "unset" state
to leave alone. Moving them is the only way the new default is the default
anywhere but a brand-new school, and the setting is one radio button in
Settings → Attendance & homework for any school that wants the old shape back.

Nothing about attendance DATA changes. The mode decides what teachers are asked
for and what denominators the capture heatmap uses; every register already taken
keeps the period it was taken on, and `classify_marked_day` reads the marked
periods themselves, not the mode.

Orgs on `twice_daily` are left exactly where they are — that mode is never an
inherited default, it is always somebody's decision.

Revision ID: a5b6c7d8e9f0
Revises: c8d9e0f1a2b3
"""

from alembic import op

revision: str = "a5b6c7d8e9f0"
down_revision: str | None = "c8d9e0f1a2b3"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE organizations "
        "ALTER COLUMN attendance_mode SET DEFAULT 'first_period'"
    )
    op.execute(
        "UPDATE organizations SET attendance_mode = 'first_period' "
        "WHERE attendance_mode = 'every_period'"
    )


def downgrade() -> None:
    # The default goes back; the rows do not. Which orgs were on `every_period`
    # by choice and which by inheritance was not recorded — it could not be —
    # so un-flipping them would be a guess dressed as a restore.
    op.execute(
        "ALTER TABLE organizations "
        "ALTER COLUMN attendance_mode SET DEFAULT 'every_period'"
    )
