"""V1-11 parent access: DOB-login lockout + the guardian inbox.

`D-13` moves parent login to school code → class → section → child → date of
birth, and `S-56` requires that a ~5,500-guess credential is not left
unprotected — hence `parent_login_attempts`, keyed per student because the
child picker names the target.

`D-08` removes WhatsApp from this version, which leaves the absence alert, the
homework notification and the Saturday note with nowhere to go — until now they
ended as lines in a log file. `guardian_messages` is that destination, and
`push_sent_at`/`unreachable_reason` are `S-62`: web push is best-effort and the
absence alert is not, so a message we could not deliver becomes a name on the
admin's board rather than a silence.

Revision ID: b0c1d2e3f4a5
Revises: a9b0c1d2e3f4
Create Date: 2026-08-02
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.core.rls import SCHOOL_PARENT_TABLES, disable_rls_sql, enable_rls_sql

revision = "b0c1d2e3f4a5"
down_revision = "a9b0c1d2e3f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── S-56 · the lockout, keyed per student ────────────────────────────
    # Platform-level (no org_id, no RLS) exactly like `otp_codes`: this row is
    # written by an unauthenticated request, before any org GUC is engaged.
    op.create_table(
        "parent_login_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["student_id"], ["students.id"],
            name=op.f("fk_parent_login_attempts_student_id_students"),
            ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_parent_login_attempts")),
        sa.UniqueConstraint("student_id", name="uq_parent_login_attempts_student"),
    )

    # ── D-08/D-14 · the family's inbox ───────────────────────────────────
    op.create_table(
        "guardian_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("guardian_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("push_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("unreachable_reason", sa.Text(), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dedupe_key", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"],
                                name=op.f("fk_guardian_messages_org_id_organizations"),
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["guardian_id"], ["guardians.id"],
                                name=op.f("fk_guardian_messages_guardian_id_guardians"),
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"],
                                name=op.f("fk_guardian_messages_student_id_students"),
                                ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_guardian_messages")),
        sa.UniqueConstraint("dedupe_key", name=op.f("uq_guardian_messages_dedupe_key")),
    )
    op.create_index(op.f("ix_guardian_messages_org_id"), "guardian_messages", ["org_id"])
    op.create_index(op.f("ix_guardian_messages_guardian_id"), "guardian_messages",
                    ["guardian_id"])
    op.create_index("ix_guardian_messages_feed", "guardian_messages",
                    ["guardian_id", "created_at"])
    op.create_index("ix_guardian_messages_reach", "guardian_messages",
                    ["org_id", "created_at", "unreachable_reason"])

    for stmt in enable_rls_sql(SCHOOL_PARENT_TABLES):
        op.execute(stmt)


def downgrade() -> None:
    for stmt in disable_rls_sql(SCHOOL_PARENT_TABLES):
        op.execute(stmt)
    op.drop_index("ix_guardian_messages_reach", table_name="guardian_messages")
    op.drop_index("ix_guardian_messages_feed", table_name="guardian_messages")
    op.drop_index(op.f("ix_guardian_messages_guardian_id"), table_name="guardian_messages")
    op.drop_index(op.f("ix_guardian_messages_org_id"), table_name="guardian_messages")
    op.drop_table("guardian_messages")
    op.drop_table("parent_login_attempts")
