"""exam_portions + calendar_events.blocks_periods (V2-P7)

`blocks_periods` turns a calendar event from whole-day-or-nothing into a partial
day: an exam that runs periods 1-3 no longer erases a whole teaching day from the
planner's capacity, it costs 3/periods_per_day of it.

`exam_portions` maps an exam_block event to the syllabus it examines, per
class-subject, so the planner can answer the question that actually matters in
June: will this portion be finished before that exam starts?

Revision ID: f6b7c8d9e0f1
Revises: f5a6b7c8d9e0
Create Date: 2026-07-09 12:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.core.rls import SCHOOL_EXAM_TABLES, disable_rls_sql, enable_rls_sql

revision: str = "f6b7c8d9e0f1"
down_revision: str | None = "f5a6b7c8d9e0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("calendar_events", sa.Column(
        "blocks_periods", postgresql.JSONB(astext_type=sa.Text()), nullable=True))

    op.create_table(
        "exam_portions",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("exam_event_id", sa.UUID(), nullable=False),
        sa.Column("class_subject_id", sa.UUID(), nullable=False),
        sa.Column("upto_topic_id", sa.UUID(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
                  nullable=False),
        sa.ForeignKeyConstraint(["class_subject_id"], ["class_subjects.id"],
                                name=op.f("fk_exam_portions_class_subject_id_class_subjects"),
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["exam_event_id"], ["calendar_events.id"],
                                name=op.f("fk_exam_portions_exam_event_id_calendar_events"),
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"],
                                name=op.f("fk_exam_portions_org_id_organizations"),
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["upto_topic_id"], ["syllabus_topics.id"],
                                name=op.f("fk_exam_portions_upto_topic_id_syllabus_topics"),
                                ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_exam_portions")),
        sa.UniqueConstraint("exam_event_id", "class_subject_id", name="uq_exam_portions_exam_cs"),
    )
    op.create_index(op.f("ix_exam_portions_org_id"), "exam_portions", ["org_id"])
    op.create_index(op.f("ix_exam_portions_exam_event_id"), "exam_portions", ["exam_event_id"])
    op.create_index(op.f("ix_exam_portions_class_subject_id"), "exam_portions",
                    ["class_subject_id"])

    for stmt in enable_rls_sql(SCHOOL_EXAM_TABLES):
        op.execute(stmt)


def downgrade() -> None:
    for stmt in disable_rls_sql(SCHOOL_EXAM_TABLES):
        op.execute(stmt)
    op.drop_table("exam_portions")
    op.drop_column("calendar_events", "blocks_periods")
