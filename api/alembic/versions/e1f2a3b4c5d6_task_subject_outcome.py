"""V1-1 (D-46): a follow-up carries its subject, and completing it records what happened.

task_instances gains:
  - subject_type / subject_id — what the task is ABOUT (student | member). The
    rail sets it, the row renders the name, the student's timeline shows the
    follow-up, and D-47's dedupe keys on it instead of walking action rows.
  - outcome — derived cache of the newest completion's "what happened?" answer.
    The truth lives on the 'completed' event payload (law 3); reopen clears the
    cache, never the event.

Revision ID: e1f2a3b4c5d6
Revises: e0f1a2b3c4d5
Create Date: 2026-08-01
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "e1f2a3b4c5d6"
down_revision = "e0f1a2b3c4d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("task_instances", sa.Column("subject_type", sa.Text(), nullable=True))
    op.add_column("task_instances",
                  sa.Column("subject_id", UUID(as_uuid=True), nullable=True))
    op.add_column("task_instances", sa.Column("outcome", sa.Text(), nullable=True))
    op.create_index(
        "ix_task_instances_subject", "task_instances",
        ["org_id", "subject_type", "subject_id"],
        postgresql_where=sa.text("subject_id IS NOT NULL"))


def downgrade() -> None:
    op.drop_index("ix_task_instances_subject", table_name="task_instances")
    op.drop_column("task_instances", "outcome")
    op.drop_column("task_instances", "subject_id")
    op.drop_column("task_instances", "subject_type")
