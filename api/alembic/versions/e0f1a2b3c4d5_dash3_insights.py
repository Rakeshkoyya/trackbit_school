"""admin operating board: substitutions + the action audit trail (DASH3-P0)

The six insight modules are computed joins over capture that already exists
(P5) — this migration adds only the two things an admin *decides* on the board
and that therefore have to be written down:

- period_substitutions: who covers an absent teacher's period. The substitution
  is the plan; `class_periods.teacher_member_id` stays the actual (P2). Live
  rows are unique per (org, date, class, period) via a PARTIAL index, so a
  cancelled cover can be replaced without losing the history.
- followup_actions: append-only (law 3), one row per action-rail button press.
  This is what stops the same guardian being reminded three times in a morning.

DASH3 §8 also listed staff_attendance and homework_results — both shipped
earlier as SF-1 (c7d8e9f0a1b2) and HW-1 (d8e9f0a1b2c3), so they are not here.

Revision ID: e0f1a2b3c4d5
Revises: d8e9f0a1b2c3
Create Date: 2026-07-29 16:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

from app.core.rls import SCHOOL_INSIGHTS_TABLES, disable_rls_sql, enable_rls_sql
from app.models.notification import NOTIF_TYPES

revision: str = "e0f1a2b3c4d5"
down_revision: str | None = "d8e9f0a1b2c3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "period_substitutions",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("class_id", sa.UUID(), nullable=False),
        sa.Column("period_no", sa.Integer(), nullable=False),
        sa.Column("class_subject_id", sa.UUID(), nullable=True),
        sa.Column("absent_member_id", sa.UUID(), nullable=True),
        sa.Column("substitute_member_id", sa.UUID(), nullable=False),
        sa.Column("created_by_member_id", sa.UUID(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("period_no >= 1",
                           name=op.f("ck_period_substitutions_substitution_period_no_valid")),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"],
                                name=op.f("fk_period_substitutions_org_id_organizations"),
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["class_id"], ["school_classes.id"],
                                name=op.f("fk_period_substitutions_class_id_school_classes"),
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["class_subject_id"], ["class_subjects.id"],
                                name=op.f("fk_period_substitutions_class_subject_id_class_subjects"),
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["absent_member_id"], ["memberships.id"],
                                name=op.f("fk_period_substitutions_absent_member_id_memberships"),
                                ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["substitute_member_id"], ["memberships.id"],
                                name=op.f("fk_period_substitutions_substitute_member_id_memberships"),
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_member_id"], ["memberships.id"],
                                name=op.f("fk_period_substitutions_created_by_member_id_memberships"),
                                ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_period_substitutions")),
    )
    op.create_index(op.f("ix_period_substitutions_org_id"), "period_substitutions", ["org_id"])
    op.create_index(op.f("ix_period_substitutions_class_id"), "period_substitutions", ["class_id"])
    op.create_index(op.f("ix_period_substitutions_substitute_member_id"),
                    "period_substitutions", ["substitute_member_id"])
    op.create_index("ix_period_substitutions_org_date", "period_substitutions",
                    ["org_id", "date"])
    # Only LIVE covers are unique — a cancelled row must not block a re-cover.
    op.create_index("uq_period_substitutions_live", "period_substitutions",
                    ["org_id", "date", "class_id", "period_no"],
                    unique=True, postgresql_where=sa.text("cancelled_at IS NULL"))

    op.create_table(
        "followup_actions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("subject_type", sa.Text(), nullable=False),
        sa.Column("subject_id", sa.UUID(), nullable=True),
        sa.Column("actor_member_id", sa.UUID(), nullable=True),
        sa.Column("target_member_id", sa.UUID(), nullable=True),
        sa.Column("detail", JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"],
                                name=op.f("fk_followup_actions_org_id_organizations"),
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_member_id"], ["memberships.id"],
                                name=op.f("fk_followup_actions_actor_member_id_memberships"),
                                ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["target_member_id"], ["memberships.id"],
                                name=op.f("fk_followup_actions_target_member_id_memberships"),
                                ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_followup_actions")),
    )
    op.create_index(op.f("ix_followup_actions_org_id"), "followup_actions", ["org_id"])
    op.create_index("ix_followup_actions_org_created", "followup_actions",
                    ["org_id", "created_at"])
    op.create_index("ix_followup_actions_subject", "followup_actions",
                    ["org_id", "subject_type", "subject_id"])

    # The substitute's notification is a new notif_type, and `notifications`
    # carries a CHECK over that column — so the constraint has to widen with it
    # or every assigned cover fails at the database.
    op.drop_constraint(op.f("ck_notifications_notif_type_valid"), "notifications",
                       type_="check")
    op.create_check_constraint(
        op.f("ck_notifications_notif_type_valid"), "notifications",
        "notif_type IN ({})".format(", ".join(f"'{t}'" for t in NOTIF_TYPES)),
    )

    # Law 2: every new org-scoped table carries the org_isolation policy.
    for stmt in enable_rls_sql(SCHOOL_INSIGHTS_TABLES):
        op.execute(stmt)


def downgrade() -> None:
    for stmt in disable_rls_sql(SCHOOL_INSIGHTS_TABLES):
        op.execute(stmt)
    op.drop_table("followup_actions")
    op.drop_table("period_substitutions")
    # Rows of the dropped type would violate the narrowed constraint, so clear
    # them first — they refer to substitutions that no longer exist anyway.
    op.execute("DELETE FROM notifications WHERE notif_type = 'substitute'")
    op.drop_constraint(op.f("ck_notifications_notif_type_valid"), "notifications",
                       type_="check")
    op.create_check_constraint(
        op.f("ck_notifications_notif_type_valid"), "notifications",
        "notif_type IN ({})".format(
            ", ".join(f"'{t}'" for t in NOTIF_TYPES if t != "substitute")),
    )
