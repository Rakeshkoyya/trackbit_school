"""package tiers — four plans, the price list, plan history, upgrade queue

`D-106`…`D-111`. Widens `plan_valid` from the inherited Free/Pro pair to the
four tiers, and adds the tables the operator's manual assignment flow needs.

Additive except for the CHECK widening, which only ever *accepts more* — so
production can migrate before the code that writes `max`/`ultra` deploys, which
is the required order here.

Two scoping rules live side by side on purpose (see `models/tiers.py`):
`plan_changes` and `upgrade_requests` carry `org_id` and get the org-isolation
policy (law 2); `plan_prices` and `upgrade_request_notes` are platform tables
with no `org_id` — the notes deliberately so, because they hold the operator's
commentary on a live negotiation and the school must never read them.

The tier list is spelled out literally here rather than imported from
`core/features.TIERS`. A migration is a historical artifact: it must keep
meaning exactly what it meant the day it ran, even after that tuple changes.

Revision ID: e8f9a0b1c2d3
Revises: d7e8f9a0b1c2
Create Date: 2026-08-08
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.core.rls import disable_rls_sql, enable_rls_sql

revision = "e8f9a0b1c2d3"
down_revision = "d7e8f9a0b1c2"
branch_labels = None
depends_on = None

_RLS_TABLES = ["plan_changes", "upgrade_requests"]

_PLANS = "'free', 'pro', 'max', 'ultra'"

# The founder's launch prices, in paise per student per month (`D-106`):
# free ₹0 · pro ₹10 · max ₹25 · ultra ₹80. Seeded so the upgrade wall can quote
# a real number on day one. These are LIST prices and are expected to move —
# that is the whole reason they are rows and not constants. A school's own rate
# is frozen separately in `plan_changes.unit_amount_snapshot`.
_SEED_PRICES = (("free", 0), ("pro", 1000), ("max", 2500), ("ultra", 8000))


def upgrade() -> None:
    # ── organizations: the four tiers, and how a plan got set ───────────────
    op.drop_constraint("plan_valid", "organizations", type_="check")
    op.create_check_constraint("plan_valid", "organizations", f"plan IN ({_PLANS})")

    op.add_column(
        "organizations",
        sa.Column("plan_source", sa.Text(), nullable=False, server_default="manual"),
    )
    op.create_check_constraint(
        "plan_source_valid", "organizations", "plan_source IN ('manual', 'billing')",
    )
    op.add_column(
        "organizations",
        sa.Column("plan_expires_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ── plan_prices — platform data, no org_id, no RLS ──────────────────────
    op.create_table(
        "plan_prices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("plan", sa.Text(), nullable=False),
        sa.Column("amount_paise_per_student", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.Text(), nullable=False, server_default="INR"),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint(f"plan IN ({_PLANS})", name="ck_plan_prices_plan_valid"),
        sa.CheckConstraint("amount_paise_per_student >= 0",
                           name="ck_plan_prices_amount_non_negative"),
    )
    op.create_index("ix_plan_prices_plan", "plan_prices", ["plan"])

    for plan, paise in _SEED_PRICES:
        op.execute(
            sa.text(
                "INSERT INTO plan_prices (plan, amount_paise_per_student, note) "
                "VALUES (:plan, :paise, 'launch list price')"
            ).bindparams(plan=plan, paise=paise)
        )

    # ── plan_changes — org-scoped, append-only (law 3) ──────────────────────
    op.create_table(
        "plan_changes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("from_plan", sa.Text(), nullable=True),
        sa.Column("to_plan", sa.Text(), nullable=False),
        sa.Column("changed_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("student_count_at_change", sa.Integer(), nullable=True),
        sa.Column("unit_amount_snapshot", sa.BigInteger(), nullable=True),
        sa.Column("monthly_amount_snapshot", sa.BigInteger(), nullable=True),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["changed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint(f"to_plan IN ({_PLANS})", name="ck_plan_changes_to_plan_valid"),
        sa.CheckConstraint(f"from_plan IS NULL OR from_plan IN ({_PLANS})",
                           name="ck_plan_changes_from_plan_valid"),
    )
    op.create_index("ix_plan_changes_org", "plan_changes", ["org_id"])

    # ── upgrade_requests — org-scoped; the school sees its own pending ask ──
    op.create_table(
        "upgrade_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requested_plan", sa.Text(), nullable=False),
        sa.Column("requested_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("feature_id", sa.Text(), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="new"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint(f"requested_plan IN ({_PLANS})",
                           name="ck_upgrade_requests_plan_valid"),
        sa.CheckConstraint("status IN ('new', 'contacted', 'won', 'lost')",
                           name="ck_upgrade_requests_status_valid"),
    )
    op.create_index("ix_upgrade_requests_org", "upgrade_requests", ["org_id"])

    # ── upgrade_request_notes — PLATFORM data, deliberately no org_id ───────
    # The operator's negotiation notes. No org_id means no join path from an
    # org-scoped query, which is the point: the school must never read them.
    op.create_table(
        "upgrade_request_notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("upgrade_request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("author_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("status_from", sa.Text(), nullable=True),
        sa.Column("status_to", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["upgrade_request_id"], ["upgrade_requests.id"],
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint("note IS NOT NULL OR status_to IS NOT NULL",
                           name="ck_upgrade_request_notes_not_empty"),
    )
    op.create_index("ix_upgrade_request_notes_request", "upgrade_request_notes",
                    ["upgrade_request_id"])

    for stmt in enable_rls_sql(_RLS_TABLES):
        op.execute(stmt)


def downgrade() -> None:
    for stmt in disable_rls_sql(_RLS_TABLES):
        op.execute(stmt)

    op.drop_index("ix_upgrade_request_notes_request", table_name="upgrade_request_notes")
    op.drop_table("upgrade_request_notes")
    op.drop_index("ix_upgrade_requests_org", table_name="upgrade_requests")
    op.drop_table("upgrade_requests")
    op.drop_index("ix_plan_changes_org", table_name="plan_changes")
    op.drop_table("plan_changes")
    op.drop_index("ix_plan_prices_plan", table_name="plan_prices")
    op.drop_table("plan_prices")

    op.drop_column("organizations", "plan_expires_at")
    op.drop_constraint("plan_source_valid", "organizations", type_="check")
    op.drop_column("organizations", "plan_source")

    # A school on max/ultra cannot satisfy the old two-value CHECK, so fold it
    # down to pro first. Lossy, and deliberately so — the alternative is a
    # downgrade that fails halfway with the constraint half-applied.
    op.execute("UPDATE organizations SET plan = 'pro' WHERE plan IN ('max', 'ultra')")
    op.drop_constraint("plan_valid", "organizations", type_="check")
    op.create_check_constraint("plan_valid", "organizations", "plan IN ('free', 'pro')")
