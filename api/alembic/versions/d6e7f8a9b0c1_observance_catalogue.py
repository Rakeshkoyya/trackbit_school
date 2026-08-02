"""events & dates: the observance catalogue, the decision log, the event-linked block (V1-7)

Three changes, and the tenancy line runs between the first two.

- `observances` — PLATFORM data (`D-60`, `S-149`): no `org_id`, no RLS policy,
  `require_super_admin` on every write, the `demo_requests` shape from EN-1. One
  curation serves every school; one correction fixes every school without a
  deploy. `source` is NOT NULL because `S-150` makes provenance the thing that
  lets an admin decide how much to trust a date.
- `event_decisions` — the school's append-only record of what it did about a
  suggestion (`S-148`, law 3). Approving also writes a `calendar_events` row;
  that row is the *effect*, this one the *record of the decision*.
- `class_periods.not_held_event_id` — `S-147`: the teacher's "not held, because"
  points at the approved event instead of forty spellings of free text, so
  "what did Diwali cost us in periods?" is answerable.

Deliberately NOT here: any birthday table. A birthday is derived from
`students.date_of_birth` (V1-2), never stored as an event (`S-121`).

Revision ID: d6e7f8a9b0c1
Revises: c5d6e7f8a9b0
Create Date: 2026-08-02 18:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.rls import SCHOOL_EVENT_TABLES, disable_rls_sql, enable_rls_sql

revision: str = "d6e7f8a9b0c1"
down_revision: str | None = "c5d6e7f8a9b0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "observances",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("kind", sa.Text(), server_default="festival", nullable=False),
        sa.Column("tier", sa.Text(), server_default="major", nullable=False),
        sa.Column("prep_days", sa.Integer(), server_default="7", nullable=False),
        sa.Column("state", sa.Text(), nullable=True),
        sa.Column("board", sa.Text(), nullable=True),
        sa.Column("tradition", sa.Text(), nullable=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_by_user_id", sa.UUID(), nullable=True),
        sa.CheckConstraint("kind IN ('holiday', 'festival', 'observance')",
                           name=op.f("ck_observances_kind_valid")),
        sa.CheckConstraint("tier IN ('major', 'minor')", name=op.f("ck_observances_tier_valid")),
        sa.CheckConstraint("end_date IS NULL OR end_date >= date",
                           name=op.f("ck_observances_range_ordered")),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"],
                                name=op.f("fk_observances_created_by_user_id_users"),
                                ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_observances")),
    )
    op.create_index(op.f("ix_observances_key"), "observances", ["key"])
    op.create_index(op.f("ix_observances_date"), "observances", ["date"])
    # One row per observance per date — re-running an importer must correct the
    # entry, never duplicate the suggestion in every school's feed.
    op.create_index("ix_observances_key_date", "observances", ["key", "date"], unique=True)

    op.create_table(
        "event_decisions",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("observance_id", sa.UUID(), nullable=True),
        sa.Column("observance_key", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("calendar_event_id", sa.UUID(), nullable=True),
        sa.Column("decided_by_member_id", sa.UUID(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.CheckConstraint("action IN ('approved', 'dismissed')",
                           name=op.f("ck_event_decisions_action_valid")),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"],
                                name=op.f("fk_event_decisions_org_id_organizations"),
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["observance_id"], ["observances.id"],
                                name=op.f("fk_event_decisions_observance_id_observances"),
                                ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["calendar_event_id"], ["calendar_events.id"],
                                name=op.f("fk_event_decisions_calendar_event_id_calendar_events"),
                                ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["decided_by_member_id"], ["memberships.id"],
                                name=op.f("fk_event_decisions_decided_by_member_id_memberships"),
                                ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_event_decisions")),
    )
    op.create_index(op.f("ix_event_decisions_org_id"), "event_decisions", ["org_id"])
    op.create_index(op.f("ix_event_decisions_observance_key"), "event_decisions",
                    ["observance_key"])
    op.create_index("ix_event_decisions_org_key", "event_decisions",
                    ["org_id", "observance_key"])

    op.add_column("class_periods", sa.Column("not_held_event_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        op.f("fk_class_periods_not_held_event_id_calendar_events"),
        "class_periods", "calendar_events", ["not_held_event_id"], ["id"], ondelete="SET NULL",
    )

    # Law 2: the org-scoped half gets the org_isolation policy. `observances`
    # does not — it has no org_id by design.
    for stmt in enable_rls_sql(SCHOOL_EVENT_TABLES):
        op.execute(stmt)


def downgrade() -> None:
    for stmt in disable_rls_sql(SCHOOL_EVENT_TABLES):
        op.execute(stmt)
    op.drop_constraint(op.f("fk_class_periods_not_held_event_id_calendar_events"),
                       "class_periods", type_="foreignkey")
    op.drop_column("class_periods", "not_held_event_id")
    op.drop_table("event_decisions")
    op.drop_index("ix_observances_key_date", table_name="observances")
    op.drop_table("observances")
