"""V1-4: half-day and late on staff attendance and leave (D-04, S-18, S-31).

SF-1 shipped staff attendance as present/absent only, with the reasoning written
down: "a teacher who arrives late is present, and the timetable already records
which period they actually took". `D-04` reverses that, and `D-78` says why it
matters — the month summary is *days worked out of working days*, and a half-day
is half a day.

The shape follows `S-18`: **no new table.** `staff_absences` is already the
exception row for a day, so it widens — `status` (absent | half_day | late) and
`portion` (am | pm, meaningful on a half-day). Present remains "no row", one row
per person per day, still a full replace. A second table would fork the truth
about one person's one day.

`leave_requests.days` becomes numeric(4,1) so a half-day is 0.5 rather than a
second column somebody has to remember to subtract. `is_half_day` + `portion`
ride along because `S-31` is right: the cover board's whole job is knowing WHICH
periods need covering, and "0.5 days" cannot answer that.

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
"""

import sqlalchemy as sa
from alembic import op

revision = "b4c5d6e7f8a9"
down_revision = "a3b4c5d6e7f8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── staff_absences: the exception row learns two more shapes ─────────────
    op.add_column("staff_absences",
                  sa.Column("status", sa.Text(), nullable=False, server_default="absent"))
    op.add_column("staff_absences", sa.Column("portion", sa.Text(), nullable=True))
    op.create_check_constraint(
        "staff_absence_status_valid", "staff_absences",
        "status IN ('absent', 'half_day', 'late')")
    op.create_check_constraint(
        "staff_absence_portion_valid", "staff_absences",
        "portion IS NULL OR portion IN ('am', 'pm')")

    # ── leave: half a day is 0.5, not a flag the arithmetic has to remember ──
    op.alter_column("leave_requests", "days",
                    existing_type=sa.Integer(),
                    type_=sa.Numeric(4, 1),
                    existing_nullable=False,
                    existing_server_default="1",
                    postgresql_using="days::numeric(4,1)")
    op.add_column("leave_requests",
                  sa.Column("is_half_day", sa.Boolean(), nullable=False,
                            server_default=sa.text("false")))
    op.add_column("leave_requests", sa.Column("portion", sa.Text(), nullable=True))
    op.create_check_constraint(
        "leave_portion_valid", "leave_requests",
        "portion IS NULL OR portion IN ('am', 'pm')")
    # A half-day is one calendar day by definition — a "half-day" spanning a week
    # is not a thing the cover board or the balance could interpret.
    op.create_check_constraint(
        "leave_half_day_single", "leave_requests",
        "is_half_day IS FALSE OR start_date = end_date")


def downgrade() -> None:
    op.drop_constraint("leave_half_day_single", "leave_requests", type_="check")
    op.drop_constraint("leave_portion_valid", "leave_requests", type_="check")
    op.drop_column("leave_requests", "portion")
    op.drop_column("leave_requests", "is_half_day")
    op.alter_column("leave_requests", "days",
                    existing_type=sa.Numeric(4, 1),
                    type_=sa.Integer(),
                    existing_nullable=False,
                    postgresql_using="ceil(days)::integer")
    op.drop_constraint("staff_absence_portion_valid", "staff_absences", type_="check")
    op.drop_constraint("staff_absence_status_valid", "staff_absences", type_="check")
    op.drop_column("staff_absences", "portion")
    op.drop_column("staff_absences", "status")
