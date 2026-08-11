"""SY-2: the chapter's manually-set teaching status.

The board's status word has always been DERIVED — a chapter is `completed`
because every topic in it was logged as taught, not because somebody said so.
That is still the default and still what an unset chapter reads.

The founder's syllabus tracker (`docs/reference/…Syllabus_ Tracker…xlsx`) has a
`Teaching Status` column a human types, and a school running its syllabus board
like that spreadsheet needs to be able to say "this one is done" on the row.
So `manual_status` is an OVERRIDE, not a replacement:

  * NULL — the normal state. The status is derived from the logs exactly as
    before, and nothing about coverage, pace or the forecast changes.
  * set — the row reads what the human said, and the board carries the derived
    word beside it so the two can never be confused.

Additive and nullable, so prod takes it with no backfill (working conventions).

Revision ID: c3d4e5f6a7b8
Revises: f9a0b1c2d3e4
"""

import sqlalchemy as sa
from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: str | None = "f9a0b1c2d3e4"
branch_labels: str | None = None
depends_on: str | None = None

_CK = "ck_syllabus_units_manual_status"


def upgrade() -> None:
    op.add_column(
        "syllabus_units",
        sa.Column("manual_status", sa.Text(), nullable=True),
    )
    op.create_check_constraint(
        _CK,
        "syllabus_units",
        "manual_status IS NULL OR manual_status IN "
        "('not_started', 'in_progress', 'completed')",
    )


def downgrade() -> None:
    op.drop_constraint(_CK, "syllabus_units", type_="check")
    op.drop_column("syllabus_units", "manual_status")
