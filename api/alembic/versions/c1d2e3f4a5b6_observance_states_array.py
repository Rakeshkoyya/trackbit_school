"""V1-19: observances.state (text) -> observances.states (text[])

The catalogue could not express the corpus it exists to hold.

`observances` carries `UNIQUE(key, date)`, which is deliberate and load-bearing:
it is what makes re-importing a corrected file *fix* every school instead of
double-suggesting to all of them (`S-151`). But it also means there is exactly
one row per observance per year — so a single `state` column could name exactly
one state per festival.

Almost nothing in the Indian calendar works that way. Onam is a public holiday
in Kerala and Lakshadweep; Chhath in Bihar, Jharkhand, UP and Delhi; Ugadi
across five southern states under three names. On the old shape the second state
imported for a festival did not fail loudly — `bulk()` upserts on (key, date),
so it quietly OVERWROTE the first, and the catalogue ended up asserting that
Onam is observed only in whichever state the importer happened to write last.

So `state` becomes `states text[]`. NULL or empty still means all-India, which
keeps the existing semantics and the existing query intent.

Safe to run anywhere: the table is platform data and was empty in every
environment at the time of writing (dev, test and DO prod all reported 0 rows).
The backfill is defensive rather than necessary, and it is written so that
re-running after a partial failure cannot double-wrap a value.

Revision ID: c1d2e3f4a5b6
Revises: b0c1d2e3f4a5
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c1d2e3f4a5b6"
down_revision: str | None = "b0c1d2e3f4a5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "observances",
        sa.Column("states", postgresql.ARRAY(sa.Text()), nullable=True),
    )
    # Defensive backfill. A single state becomes a one-element array; NULL and
    # blank stay NULL, because "" and "all India" must not become the array
    # [''], which matches no school and is invisible in every UI.
    op.execute(
        """
        UPDATE observances
           SET states = ARRAY[state]
         WHERE state IS NOT NULL
           AND btrim(state) <> ''
           AND states IS NULL
        """
    )
    op.drop_column("observances", "state")

    # The read is `:school_state = ANY(states)`, once per admin opening the
    # suggestions queue. GIN over the array keeps that an index lookup rather
    # than a scan as the corpus grows year on year.
    op.create_index(
        "ix_observances_states",
        "observances",
        ["states"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_observances_states", table_name="observances")
    op.add_column("observances", sa.Column("state", sa.Text(), nullable=True))
    # Lossy on purpose, and the only honest option: a text column cannot hold a
    # set. The first state is kept so a downgraded row is still scoped
    # somewhere rather than silently becoming all-India, which would show every
    # school every regional holiday in the country.
    op.execute(
        """
        UPDATE observances
           SET state = states[1]
         WHERE states IS NOT NULL
           AND array_length(states, 1) >= 1
        """
    )
    op.drop_column("observances", "states")
