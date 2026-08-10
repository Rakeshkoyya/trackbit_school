"""FE-1 — the fee desk.

Five changes, all additive, plus one data normalisation that has to happen
before an index can hold the rule it enforces.

**`class_name` becomes the class, not the section (`D-116`).** The founder priced
per class: one structure for "6" covers 6-A, 6-B and 6-C. The old create screen
wrote a *sectioned* label (`"6-B"`) into `class_name`, so this migration rewrites
any such row back to its bare class name — but only where the suffix really is a
section of a real class in the same org and year, and only where the existing
value is not itself a valid class name. Anything it cannot prove is left exactly
as it is: a wrong guess here silently reprices a school.

Normalisation can collide two active structures onto one key, so duplicates are
archived (newest wins, `is_active = false` — never deleted) and a partial unique
index then makes the collision impossible. The service has always *tried* to
guarantee one active structure per key in Python; until now nothing enforced it.

**`is_voided` is a stored column, not a derived word (`D-127`).** Every other
instalment state is computed by `fee_math` on read, deliberately — but voiding is
a *decision a person made*, and `recompute_student_fee` runs after every mutation
and would cheerfully un-void it on the next payment. Law 3 also wants the row
kept rather than deleted, so the transfer can be undone.

**`fee_events` is the actor log (`D-124`).** The founder's case, in his words:
three admins share the fee desk, one changes something, another notices and needs
to know who to ask. `fee_transactions` cannot answer that — it is a *money*
ledger, and a third of what needs logging (structure edits) has no student
attached at all.

Revision ID: b7c8d9e0f1a2
Revises: d4e5f6a7b8c9a
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.core.rls import SCHOOL_FEE_DESK_TABLES, disable_rls_sql, enable_rls_sql

revision: str = "b7c8d9e0f1a2"
down_revision: str | None = "d4e5f6a7b8c9a"
branch_labels: str | None = None
depends_on: str | None = None

_NIL = "'00000000-0000-0000-0000-000000000000'::uuid"
_UQ_ACTIVE = "uq_fee_structures_active_key"


def upgrade() -> None:
    # ── D-116: class_name holds the CLASS, never the section ─────────────────
    # Only rewrite "6-B" -> "6" when (a) the suffix is a real section of a real
    # class in this org+year, and (b) "6-B" is not itself the name of a class.
    op.execute(
        """
        UPDATE fee_structures AS fs
           SET class_name = sc.name
          FROM school_classes AS sc
         WHERE sc.org_id = fs.org_id
           AND sc.academic_year_id = fs.academic_year_id
           AND sc.section IS NOT NULL
           AND sc.section <> ''
           AND fs.class_name = sc.name || '-' || sc.section
           AND NOT EXISTS (
                 SELECT 1 FROM school_classes AS s2
                  WHERE s2.org_id = fs.org_id
                    AND s2.academic_year_id = fs.academic_year_id
                    AND s2.name = fs.class_name
               );
        """
    )

    # Normalising can land two active structures on one key. Newest wins; the
    # rest are ARCHIVED, never deleted — the school's pricing history survives.
    op.execute(
        f"""
        UPDATE fee_structures SET is_active = false
         WHERE id IN (
               SELECT id FROM (
                      SELECT id,
                             ROW_NUMBER() OVER (
                                 PARTITION BY org_id, academic_year_id, class_name,
                                              COALESCE(category_id, {_NIL})
                                 ORDER BY created_at DESC, id DESC
                             ) AS rn
                        FROM fee_structures
                       WHERE is_active
               ) AS ranked
                WHERE ranked.rn > 1
         );
        """
    )

    op.execute(
        f"""
        CREATE UNIQUE INDEX {_UQ_ACTIVE} ON fee_structures (
            org_id, academic_year_id, class_name, COALESCE(category_id, {_NIL})
        ) WHERE is_active;
        """
    )

    # ── the payment date belongs to the payment ──────────────────────────────
    # `pay()` has always accepted `paid_on` and written it to the INSTALMENT,
    # so a second payment overwrote the first one's date and the ledger could
    # only say when the row was created. A receipt needs the date on the money.
    op.add_column("fee_transactions", sa.Column("paid_on", sa.Date(), nullable=True))

    # ── D-127: a transferred student's record closes, reversibly ─────────────
    op.add_column("student_fees",
                  sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("student_fees", sa.Column("closed_reason", sa.Text(), nullable=True))
    op.add_column(
        "student_fees",
        sa.Column("closed_by_member_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_student_fees_closed_by_member_id"), "student_fees", "memberships",
        ["closed_by_member_id"], ["id"], ondelete="SET NULL",
    )
    op.add_column(
        "installments",
        sa.Column("is_voided", sa.Boolean(), server_default=sa.false(), nullable=False),
    )

    # ── D-128: one receipt sequence per org + academic year ──────────────────
    op.create_table(
        "fee_receipt_counters",
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("academic_year_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("prefix", sa.Text(), server_default="FR", nullable=False),
        sa.Column("next_seq", sa.Integer(), server_default="1", nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["academic_year_id"], ["academic_years.id"],
                                ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("org_id", "academic_year_id"),
    )

    # ── D-122/D-123: proof of payment ────────────────────────────────────────
    op.create_table(
        "fee_payment_proofs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("transaction_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("student_fee_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        # The KEY, never a URL: presigned GETs expire, so URLs are minted per read.
        sa.Column("object_key", sa.Text(), nullable=False),
        sa.Column("content_type", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("uploaded_by_member_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        # D-123: soft delete. A misfiled receipt is a real privacy problem and
        # must be removable; that it EXISTED is history and stays.
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by_member_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["transaction_id"], ["fee_transactions.id"],
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_fee_id"], ["student_fees.id"],
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by_member_id"], ["memberships.id"],
                                ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["deleted_by_member_id"], ["memberships.id"],
                                ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("kind IN ('photo', 'pdf')",
                           name=op.f("ck_fee_payment_proofs_kind")),
    )
    op.create_index(op.f("ix_fee_payment_proofs_org_id"), "fee_payment_proofs", ["org_id"])
    op.create_index(op.f("ix_fee_payment_proofs_transaction_id"), "fee_payment_proofs",
                    ["transaction_id"])
    op.create_index(op.f("ix_fee_payment_proofs_student_fee_id"), "fee_payment_proofs",
                    ["student_fee_id"])

    # ── D-124: who did what ──────────────────────────────────────────────────
    op.create_table(
        "fee_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        # Nullable: a structure edit belongs to no student, and that is the whole
        # reason this table exists rather than more rows in the money ledger.
        sa.Column("student_fee_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("fee_structure_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("academic_year_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("kind", sa.Text(), nullable=False),
        # A finished sentence, written at write time. No reader re-derives the
        # wording — the same reason `created_by_name` is denormalised on the ledger.
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()),
                  server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("actor_member_id", postgresql.UUID(as_uuid=True), nullable=True),
        # Denormalised on purpose: the log outlives the account that wrote it.
        sa.Column("actor_name", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_fee_id"], ["student_fees.id"],
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["fee_structure_id"], ["fee_structures.id"],
                                ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["academic_year_id"], ["academic_years.id"],
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_member_id"], ["memberships.id"],
                                ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_fee_events_org_id"), "fee_events", ["org_id"])
    op.execute(
        "CREATE INDEX ix_fee_events_student_fee ON fee_events "
        "(student_fee_id, created_at DESC);"
    )
    op.execute(
        "CREATE INDEX ix_fee_events_year ON fee_events "
        "(academic_year_id, created_at DESC);"
    )

    # Law 2: every new org-scoped table carries the org_isolation policy.
    for stmt in enable_rls_sql(SCHOOL_FEE_DESK_TABLES):
        op.execute(stmt)


def downgrade() -> None:
    for stmt in disable_rls_sql(SCHOOL_FEE_DESK_TABLES):
        op.execute(stmt)
    op.drop_table("fee_events")
    op.drop_table("fee_payment_proofs")
    op.drop_table("fee_receipt_counters")
    op.drop_column("installments", "is_voided")
    op.drop_constraint(op.f("fk_student_fees_closed_by_member_id"), "student_fees",
                       type_="foreignkey")
    op.drop_column("student_fees", "closed_by_member_id")
    op.drop_column("student_fees", "closed_reason")
    op.drop_column("student_fees", "closed_at")
    op.drop_column("fee_transactions", "paid_on")
    op.execute(f"DROP INDEX IF EXISTS {_UQ_ACTIVE};")
    # The class_name normalisation is NOT reversed: "6" is the correct value and
    # re-appending a section would have to guess which one.
