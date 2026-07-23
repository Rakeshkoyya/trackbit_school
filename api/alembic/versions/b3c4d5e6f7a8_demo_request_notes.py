"""demo_request_notes: the operator's append-only history on a lead

Every status move and every remark is one row here; `demo_requests.status` stays
as the derived cache of the newest `status_to` (law 3 — the same shape as
`plans.status` over `plan_approvals`). Platform-level like its parent: a lead
exists before its school has an org, so there is no org_id and no RLS policy.

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-07-23 16:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b3c4d5e6f7a8"
down_revision: str | None = "a2b3c4d5e6f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "demo_request_notes",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("demo_request_id", sa.UUID(), nullable=False),
        sa.Column("author_user_id", sa.UUID(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("status_from", sa.Text(), nullable=True),
        sa.Column("status_to", sa.Text(), nullable=True),
        sa.CheckConstraint("note IS NOT NULL OR status_to IS NOT NULL",
                           name=op.f("ck_demo_request_notes_not_empty")),
        sa.ForeignKeyConstraint(["demo_request_id"], ["demo_requests.id"],
                                name=op.f("fk_demo_request_notes_demo_request_id_demo_requests"),
                                ondelete="CASCADE"),
        # SET NULL: the history outlives the operator account that wrote it.
        sa.ForeignKeyConstraint(["author_user_id"], ["users.id"],
                                name=op.f("fk_demo_request_notes_author_user_id_users"),
                                ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_demo_request_notes")),
    )
    op.create_index(op.f("ix_demo_request_notes_demo_request_id"),
                    "demo_request_notes", ["demo_request_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_demo_request_notes_demo_request_id"),
                  table_name="demo_request_notes")
    op.drop_table("demo_request_notes")
