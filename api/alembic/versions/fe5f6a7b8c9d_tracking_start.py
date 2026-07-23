"""mid-year adoption: academic_years.tracking_start_date

A school can adopt TrackBit after its year began (even after Term 1 exams).
`tracking_start_date` records that adoption date (NULL = tracked from the year's
start). The rule it encodes: data before this date is "before our time" — shown
as no-data, never as a red/amber warning; planning windows clamp to it so plans
made after adoption only schedule the remaining stretch of the year.

Revision ID: fe5f6a7b8c9d
Revises: fd4e5f6a7b8c
Create Date: 2026-07-20 09:30:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "fe5f6a7b8c9d"
down_revision: str | None = "fd4e5f6a7b8c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("academic_years",
                  sa.Column("tracking_start_date", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("academic_years", "tracking_start_date")
