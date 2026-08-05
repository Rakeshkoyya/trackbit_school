"""the class teacher's own log about a child (founder, 2026-08-05)

`student_notes` — one table, append-only (law 3), staff-only.

Every other thing the school knows about a child is a byproduct of doing the
work (P5): attendance is a tap, coverage is a lesson log, a band is a test. This
is the one deliberate exception and it belongs to the class teacher: the thing
she noticed that no capture surface has a field for — a child who has gone quiet,
a conversation at the gate, a week that turned around.

Shape copied from `fee_notes` / `demo_request_notes` / `plan_approvals`: nothing
is ever edited, a correction is a new row, and `author_member_id` is SET NULL so
the history outlives the account. What a teacher thought in September stays in
the record when November disagrees; a log that can be quietly rewritten is not a
log.

It is deliberately NOT reachable from the parent portal. `services/
parent_portal.py` is an allowlist projection built field by field, so this stays
out by construction rather than by anyone remembering to exclude it.

Revision ID: c2d3e4f5a6b7
Revises: c1d2e3f4a5b6
Create Date: 2026-08-05 10:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.rls import SCHOOL_STUDENT_NOTE_TABLES, disable_rls_sql, enable_rls_sql

revision: str = "c2d3e4f5a6b7"
down_revision: str | None = "c1d2e3f4a5b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "student_notes",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("student_id", sa.UUID(), nullable=False),
        # A short fixed list on purpose: the value of the log is reading a year
        # of it in one scroll, and forty spellings of "spoke to parent" is a
        # diary rather than a record.
        sa.Column("kind", sa.Text(), server_default="general", nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("author_member_id", sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_member_id"], ["memberships.id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            "kind IN ('general', 'behaviour', 'wellbeing', 'achievement', "
            "'parent_contact', 'concern')",
            name="ck_student_notes_kind",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_student_notes_org_id", "student_notes", ["org_id"])
    op.create_index("ix_student_notes_student_id", "student_notes", ["student_id"])
    # The one read the screen makes: this child's log, newest first.
    op.create_index("ix_student_notes_student_created", "student_notes",
                    ["student_id", sa.text("created_at DESC")])

    for stmt in enable_rls_sql(SCHOOL_STUDENT_NOTE_TABLES):
        op.execute(stmt)


def downgrade() -> None:
    for stmt in disable_rls_sql(SCHOOL_STUDENT_NOTE_TABLES):
        op.execute(stmt)
    op.drop_index("ix_student_notes_student_created", table_name="student_notes")
    op.drop_index("ix_student_notes_student_id", table_name="student_notes")
    op.drop_index("ix_student_notes_org_id", table_name="student_notes")
    op.drop_table("student_notes")
