"""a chapter the school has decided is not in scope (founder, 2026-08-08)

The syllabus board already had four words for a chapter, and all four were
*derived* — `chapter_status()` reads topics, lesson logs and plan entries and
decides. That is right for teaching status and wrong for one thing it cannot
know: whether the school ever intended to teach the chapter at all.

Without somewhere to say so, an out-of-scope chapter — an optional unit, a
chapter the board dropped this year, a section the school teaches in a different
grade — sits on the board forever as `not_scheduled`, and every coverage figure
counts it in the denominator. A school with 30 chapters of which it teaches 24
reads as permanently 20% short. That is rule 2 inverted: a gap in the *record*
rendered as a failure by a *person*.

So this is a stored DECISION beside four derived states, and it does exactly two
things:

**1. It forces the status.** `core/coverage.py::chapter_status(excluded=True)`
returns `not_scheduled` regardless of logs. The decision lives in the owner
module, not at the call sites — the same rule every other coverage word follows.

**2. It leaves the denominator.** `services/coverage.py::_topics` skips the
chapter, so its topics are out of the numerator AND the denominator. That is not
a new mechanism: pre-tracking chapters (a school adopting TrackBit mid-year) are
skipped on the line above, for the same reason and with the same one-line shape.
Every surface reading `CoverageService` inherits it at once — the syllabus
board, the admin dashboard's syllabus tab, the growth report, the parent
progress screen and Lucy's tools.

    ⚠️ It is deliberately NOT a fifth status word. `not_scheduled` already
    means "nobody promised this", and a chapter excluded on purpose and a
    chapter nobody got round to planning are the same fact to every reader:
    there is nothing to be behind on. Adding `excluded` as its own word would
    have meant a new state in three TypeScript unions, the parent report and
    every `STATUS_LABEL` map, to draw a distinction only the person who set the
    flag can act on. The flag itself is the record of the decision.

Additive and defaulted, so prod can migrate before the code deploys.
"""

import sqlalchemy as sa
from alembic import op

revision = "b5c6d7e8f9a0"
down_revision = "a4b5c6d7e8f9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "syllabus_units",
        sa.Column("not_planned", sa.Boolean(), nullable=False,
                  server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("syllabus_units", "not_planned")
