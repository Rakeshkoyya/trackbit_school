"""per-student session capture (HS-2)

Two founder-driven changes to hostel sessions:

`session_media.student_id` (nullable) — a memory can now belong to one student
(their work, their moment) instead of only the whole meeting. NULL keeps the
class-wide behaviour; existing rows are untouched. Explicit founder call, July
2026 — supersedes the batch-only reading of P5 for hostel sessions.

`session_student_logs.section` — a student's study log becomes named sections
("Maths", "Revision") like the class deep log: one row per (meeting, student,
section), full-replaced per student on save. Existing single-note rows become
the '' (unnamed) section.

Revision ID: f9e0f1a2b3c4
Revises: f8d9e0f1a2b3
Create Date: 2026-07-12 10:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f9e0f1a2b3c4"
down_revision: str | None = "f8d9e0f1a2b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("session_media", sa.Column("student_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        op.f("fk_session_media_student_id_students"), "session_media", "students",
        ["student_id"], ["id"], ondelete="CASCADE")

    op.add_column("session_student_logs",
                  sa.Column("section", sa.Text(), nullable=False, server_default=""))
    op.drop_constraint("uq_session_student_logs_meeting_id", "session_student_logs",
                       type_="unique")
    op.create_unique_constraint("uq_session_student_logs_meeting_id", "session_student_logs",
                                ["meeting_id", "student_id", "section"])


def downgrade() -> None:
    # Collapsing sections back to one row per student would lose data; keep the
    # first section per (meeting, student) and drop the rest.
    op.execute("""
        DELETE FROM session_student_logs a USING session_student_logs b
        WHERE a.meeting_id = b.meeting_id AND a.student_id = b.student_id
          AND a.created_at > b.created_at
    """)
    op.drop_constraint("uq_session_student_logs_meeting_id", "session_student_logs",
                       type_="unique")
    op.create_unique_constraint("uq_session_student_logs_meeting_id", "session_student_logs",
                                ["meeting_id", "student_id"])
    op.drop_column("session_student_logs", "section")

    op.drop_constraint(op.f("fk_session_media_student_id_students"), "session_media",
                       type_="foreignkey")
    op.drop_column("session_media", "student_id")
