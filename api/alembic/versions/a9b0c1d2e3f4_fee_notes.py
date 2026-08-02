"""fees: the conversation history, and a notification type for the reminder (V1-10)

Two changes, and the module needs nothing else — `D-62` is read + remind, so the
money math, the ledger and the counter screen are untouched.

- `fee_notes` (`D-84`) — an **append-only** log per student fee: who spoke to
  whom, when, and **what the family said**. The founder's own words: *"I know —
  conversation history. I want you to maintain this for every student."* It
  renders on `/fees/[id]` and travels into the follow-up task, so the next
  caller is not the fourth person this month to ask the same question.

  Same shape as `demo_request_notes` / `plan_approvals` / `leave_request_events`
  (law 3): nothing is ever edited, the newest row is the current state, and
  `author_member_id` is SET NULL so the history outlives the account.

- `notifications.notif_type` gains `fee_reminder`. It is a CHECK constraint, so
  a new type needs a migration — the `substitute` precedent from DASH3.

Deliberately NOT here: any new fee table. A quarter is a **computed window** over
due dates (`Q-67`/`S-153`), not a column; and the reminder's idempotence reuses
`followup_actions`, whose `kind` is free text.

Revision ID: a9b0c1d2e3f4
Revises: f8a9b0c1d2e3
Create Date: 2026-08-02 23:30:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.rls import SCHOOL_FEE_NOTE_TABLES, disable_rls_sql, enable_rls_sql
from app.models.notification import NOTIF_TYPES

revision: str = "a9b0c1d2e3f4"
down_revision: str | None = "f8a9b0c1d2e3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_TYPES = tuple(t for t in NOTIF_TYPES if t != "fee_reminder")


def upgrade() -> None:
    op.create_table(
        "fee_notes",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("student_fee_id", sa.UUID(), nullable=False),
        # call | visit | message | reminder | assigned | note — how the school
        # reached the family, or what the school did about it.
        sa.Column("kind", sa.Text(), server_default="call", nullable=False),
        # **What the family said.** The point of the whole table: "spoke to the
        # father — paying after the 15th" is what makes a row go away; "reminded"
        # is only an event.
        sa.Column("said", sa.Text(), nullable=True),
        sa.Column("promised_date", sa.Date(), nullable=True),
        sa.Column("author_member_id", sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"],
                                name=op.f("fk_fee_notes_org_id_organizations"),
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_fee_id"], ["student_fees.id"],
                                name=op.f("fk_fee_notes_student_fee_id_student_fees"),
                                ondelete="CASCADE"),
        # SET NULL: the conversation outlives the person who had it.
        sa.ForeignKeyConstraint(["author_member_id"], ["memberships.id"],
                                name=op.f("fk_fee_notes_author_member_id_memberships"),
                                ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_fee_notes")),
    )
    op.create_index(op.f("ix_fee_notes_org_id"), "fee_notes", ["org_id"])
    op.create_index(op.f("ix_fee_notes_student_fee_id"), "fee_notes", ["student_fee_id"])

    op.drop_constraint(op.f("ck_notifications_notif_type_valid"), "notifications",
                       type_="check")
    op.create_check_constraint(
        op.f("ck_notifications_notif_type_valid"), "notifications",
        "notif_type IN ({})".format(", ".join(f"'{t}'" for t in NOTIF_TYPES)))

    for stmt in enable_rls_sql(SCHOOL_FEE_NOTE_TABLES):
        op.execute(stmt)


def downgrade() -> None:
    for stmt in disable_rls_sql(SCHOOL_FEE_NOTE_TABLES):
        op.execute(stmt)
    op.execute("DELETE FROM notifications WHERE notif_type = 'fee_reminder'")
    op.drop_constraint(op.f("ck_notifications_notif_type_valid"), "notifications",
                       type_="check")
    op.create_check_constraint(
        op.f("ck_notifications_notif_type_valid"), "notifications",
        "notif_type IN ({})".format(", ".join(f"'{t}'" for t in _OLD_TYPES)))
    op.drop_index(op.f("ix_fee_notes_student_fee_id"), table_name="fee_notes")
    op.drop_index(op.f("ix_fee_notes_org_id"), table_name="fee_notes")
    op.drop_table("fee_notes")
