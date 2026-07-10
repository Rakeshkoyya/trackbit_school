"""term-scoped planning (V2-P11)

Three changes, one idea: a school plans a term at a time.

`syllabus_units.term_id` lets a chapter say which term it belongs to. NULL keeps
the whole-year behaviour, so existing rows and schools that never use terms are
untouched.

`syllabus_topics.est_periods` becomes NULLABLE. NULL = "not sized yet", the normal
state of Term 2's chapters in April. Previously the column was NOT NULL DEFAULT 1,
so an unplanned chapter was indistinguishable from a one-period chapter, and the
forecast reported green on a year nobody had planned. Existing rows keep their
numbers; nothing is backfilled to NULL.

`plan_approvals` is an append-only log of baseline locks per (class-subject, term).
Un-approving appends `action='revoke'` rather than mutating the approval, so the
history of who unlocked a baseline survives (law 3). It also makes the error
message "Un-approving is a separate action" true for the first time — that action
never existed.

Revision ID: f7c8d9e0f1a2
Revises: f6b7c8d9e0f1
Create Date: 2026-07-10 10:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.rls import SCHOOL_PLAN_APPROVAL_TABLES, disable_rls_sql, enable_rls_sql

revision: str = "f7c8d9e0f1a2"
down_revision: str | None = "f6b7c8d9e0f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("syllabus_units", sa.Column("term_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        op.f("fk_syllabus_units_term_id_terms"), "syllabus_units", "terms",
        ["term_id"], ["id"], ondelete="SET NULL")
    op.create_index(op.f("ix_syllabus_units_term_id"), "syllabus_units", ["term_id"])

    # Drop the server default first: otherwise every future INSERT that omits
    # est_periods silently gets 1 back, which is the bug this migration exists to
    # remove. Existing rows keep whatever number they already have.
    op.alter_column("syllabus_topics", "est_periods",
                    existing_type=sa.Integer(), nullable=True, server_default=None)

    op.create_table(
        "plan_approvals",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("class_subject_id", sa.UUID(), nullable=False),
        sa.Column("term_id", sa.UUID(), nullable=True),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("actor_user_id", sa.UUID(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
                  nullable=False),
        sa.CheckConstraint("action IN ('approve', 'revoke')",
                           name=op.f("ck_plan_approvals_plan_approval_action_valid")),
        sa.ForeignKeyConstraint(["class_subject_id"], ["class_subjects.id"],
                                name=op.f("fk_plan_approvals_class_subject_id_class_subjects"),
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"],
                                name=op.f("fk_plan_approvals_org_id_organizations"),
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["term_id"], ["terms.id"],
                                name=op.f("fk_plan_approvals_term_id_terms"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"],
                                name=op.f("fk_plan_approvals_actor_user_id_users"),
                                ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_plan_approvals")),
    )
    op.create_index(op.f("ix_plan_approvals_org_id"), "plan_approvals", ["org_id"])
    op.create_index(op.f("ix_plan_approvals_class_subject_id"), "plan_approvals",
                    ["class_subject_id"])
    op.create_index(op.f("ix_plan_approvals_term_id"), "plan_approvals", ["term_id"])
    # "latest row for this (class-subject, term)" is the only read shape.
    op.create_index("ix_plan_approvals_cs_term_created", "plan_approvals",
                    ["class_subject_id", "term_id", "created_at"])

    # Backfill: an already-approved plan becomes a whole-year approval, so the
    # baselines locked before this migration stay locked.
    op.execute("""
        INSERT INTO plan_approvals (org_id, class_subject_id, term_id, action, actor_user_id,
                                    created_at)
        SELECT org_id, class_subject_id, NULL, 'approve', approved_by,
               COALESCE(approved_at, now())
        FROM plans WHERE status = 'approved'
    """)

    for stmt in enable_rls_sql(SCHOOL_PLAN_APPROVAL_TABLES):
        op.execute(stmt)


def downgrade() -> None:
    for stmt in disable_rls_sql(SCHOOL_PLAN_APPROVAL_TABLES):
        op.execute(stmt)
    op.drop_table("plan_approvals")

    # Anything unsized has to become a number again to satisfy NOT NULL. 1 is the
    # value this migration was written to stop meaning "unknown", but on the way
    # back down it is the only option.
    op.execute("UPDATE syllabus_topics SET est_periods = 1 WHERE est_periods IS NULL")
    op.alter_column("syllabus_topics", "est_periods",
                    existing_type=sa.Integer(), nullable=False, server_default="1")

    op.drop_index(op.f("ix_syllabus_units_term_id"), table_name="syllabus_units")
    op.drop_constraint(op.f("fk_syllabus_units_term_id_terms"), "syllabus_units",
                       type_="foreignkey")
    op.drop_column("syllabus_units", "term_id")
