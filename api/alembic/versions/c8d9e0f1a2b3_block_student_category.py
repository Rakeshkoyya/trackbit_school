"""One student-category vocabulary, referenced by id (`D-129`).

A block that runs for hostellers only used to say so with a boolean, and the
roster query then resolved it by **matching the category name as a string**:

    WHERE lower(student_categories.name) = 'hosteller'

Two ways that breaks, and both are the kind a school finds rather than a test.
Rename the category to "Hostel" in Settings and every hosteller block silently
serves an empty roster. Add a third category — "Transport", "Staff ward" — and a
block cannot be restricted to it at all, because the only question the model can
ask is *"hostellers: yes or no"*.

So a block now points at a **category row**, like everything else does. The
founder's framing: *"lets make this as configuration so we can put this editing
under org settings and then it will reflect every where"*.

`hostellers_only` is **kept and frozen**, not dropped. Prod is migrated before
code deploys (working conventions), so removing a column the running app still
selects would break the window in between. Nothing reads or writes it after this
revision; a later migration can drop it once no deployed build refers to it.

The backfill only fires where it can prove the mapping — a session flagged
hostellers-only in an org that actually has a category named "hosteller". Any
session it cannot resolve keeps a NULL category, which means "everyone in the
class", which is what an unresolvable flag should degrade to.

Revision ID: c8d9e0f1a2b3
Revises: b7c8d9e0f1a2
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "c8d9e0f1a2b3"
down_revision: str | None = "b7c8d9e0f1a2"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "sessions",
        sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_sessions_category_id"), "sessions", "student_categories",
        ["category_id"], ["id"], ondelete="SET NULL",
    )
    op.create_index(op.f("ix_sessions_category_id"), "sessions", ["category_id"])

    # Backfill only what can be proven: same org, and a category actually named
    # "hosteller". Everything else stays NULL = the whole class.
    op.execute(
        """
        UPDATE sessions AS s
           SET category_id = c.id
          FROM student_categories AS c
         WHERE c.org_id = s.org_id
           AND lower(c.name) = 'hosteller'
           AND s.hostellers_only IS TRUE
           AND s.category_id IS NULL;
        """
    )


def downgrade() -> None:
    # `hostellers_only` was never cleared, so the old behaviour is still intact
    # underneath and dropping the column loses nothing.
    op.drop_index(op.f("ix_sessions_category_id"), table_name="sessions")
    op.drop_constraint(op.f("fk_sessions_category_id"), "sessions",
                       type_="foreignkey")
    op.drop_column("sessions", "category_id")
