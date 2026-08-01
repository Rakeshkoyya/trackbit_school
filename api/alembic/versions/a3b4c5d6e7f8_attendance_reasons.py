"""V1-3 — attendance reasons, informed absence, and the class teacher's inputs.

- attendance_exceptions gains reason_code/reason_note/reason_by/reason_at
  (D-02: the reason is added AFTER capture, by admin or teacher, never at the
  moment of marking — capture stays one tap).
- student_absence_notes (NEW, append-only — law 3): informed/planned absence
  ("away 12–15 Aug, family function") and follow-up outcomes. A covering note
  pre-explains the days, suppresses the guardian alert (S-13), and keeps the
  child amber on the board with the reason visible (S-24/S-21). Corrections are
  new rows, never edits.
- students.enrolled_on (S-02): a September joiner's denominator starts the day
  they joined, not the class's whole marked history.
- organizations.phone: the school number behind the parent's "tell the school
  why" tel: link (S-25) — reads only, parents never write (D-86).

Revision ID: a3b4c5d6e7f8
Revises: f2a3b4c5d6e7
Create Date: 2026-08-01
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from app.core.rls import SCHOOL_ABSENCE_TABLES, disable_rls_sql, enable_rls_sql

revision = "a3b4c5d6e7f8"
down_revision = "f2a3b4c5d6e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("attendance_exceptions", sa.Column("reason_code", sa.Text(), nullable=True))
    op.add_column("attendance_exceptions", sa.Column("reason_note", sa.Text(), nullable=True))
    op.add_column("attendance_exceptions", sa.Column(
        "reason_by_member_id", UUID(as_uuid=True),
        sa.ForeignKey("memberships.id", ondelete="SET NULL"), nullable=True))
    op.add_column("attendance_exceptions", sa.Column(
        "reason_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "student_absence_notes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("student_id", UUID(as_uuid=True),
                  sa.ForeignKey("students.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("from_date", sa.Date(), nullable=False),
        sa.Column("to_date", sa.Date(), nullable=False),
        sa.Column("reason_code", sa.Text(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("source", sa.Text(), nullable=False, server_default="office"),
        sa.Column("created_by_member_id", UUID(as_uuid=True),
                  sa.ForeignKey("memberships.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.CheckConstraint("to_date >= from_date", name="ck_absence_notes_range"),
        sa.CheckConstraint("source IN ('parent_call', 'office', 'teacher')",
                           name="ck_absence_notes_source"),
    )
    op.create_index("ix_absence_notes_student_window", "student_absence_notes",
                    ["org_id", "student_id", "from_date"])

    op.add_column("students", sa.Column("enrolled_on", sa.Date(), nullable=True))
    op.add_column("organizations", sa.Column("phone", sa.Text(), nullable=True))

    for stmt in enable_rls_sql(SCHOOL_ABSENCE_TABLES):
        op.execute(stmt)


def downgrade() -> None:
    for stmt in disable_rls_sql(SCHOOL_ABSENCE_TABLES):
        op.execute(stmt)
    op.drop_column("organizations", "phone")
    op.drop_column("students", "enrolled_on")
    op.drop_index("ix_absence_notes_student_window", table_name="student_absence_notes")
    op.drop_table("student_absence_notes")
    for col in ("reason_at", "reason_by_member_id", "reason_note", "reason_code"):
        op.drop_column("attendance_exceptions", col)
