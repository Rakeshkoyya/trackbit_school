"""fee port: structures/templates/student_fees/installments/transactions (SPRD §4.6)

Revision ID: d3f4a5b6c7d8
Revises: d2e3f4a5b6c7
Create Date: 2026-07-07 12:15:00.000000

Ported from fee_management_system onto org_id + RLS. fee_transactions is
append-only (undo = compensating row).
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.rls import SCHOOL_FEE_TABLES, disable_rls_sql, enable_rls_sql

revision: str = "d3f4a5b6c7d8"
down_revision: str | None = "d2e3f4a5b6c7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_MONEY = sa.Numeric(12, 2)


def upgrade() -> None:
    op.create_table(
        "fee_structures",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("class_name", sa.Text(), nullable=False),
        sa.Column("category_id", sa.UUID(), nullable=True),
        sa.Column("academic_year_id", sa.UUID(), nullable=False),
        sa.Column("total_amount", _MONEY, nullable=False),
        sa.Column("num_installments", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["academic_year_id"], ["academic_years.id"], name=op.f("fk_fee_structures_academic_year_id_academic_years"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["category_id"], ["student_categories.id"], name=op.f("fk_fee_structures_category_id_student_categories"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name=op.f("fk_fee_structures_created_by_users"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], name=op.f("fk_fee_structures_org_id_organizations"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_fee_structures")),
    )
    op.create_index(op.f("ix_fee_structures_org_id"), "fee_structures", ["org_id"])

    op.create_table(
        "fee_installment_templates",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("fee_structure_id", sa.UUID(), nullable=False),
        sa.Column("installment_number", sa.Integer(), nullable=False),
        sa.Column("label", sa.Text(), nullable=True),
        sa.Column("amount", _MONEY, nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.ForeignKeyConstraint(["fee_structure_id"], ["fee_structures.id"], name=op.f("fk_fee_installment_templates_fee_structure_id_fee_structures"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], name=op.f("fk_fee_installment_templates_org_id_organizations"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_fee_installment_templates")),
    )
    op.create_index(op.f("ix_fee_installment_templates_fee_structure_id"), "fee_installment_templates", ["fee_structure_id"])
    op.create_index(op.f("ix_fee_installment_templates_org_id"), "fee_installment_templates", ["org_id"])

    op.create_table(
        "student_fees",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("student_id", sa.UUID(), nullable=False),
        sa.Column("fee_structure_id", sa.UUID(), nullable=True),
        sa.Column("academic_year_id", sa.UUID(), nullable=False),
        sa.Column("total_fee", _MONEY, nullable=False),
        sa.Column("discount", _MONEY, server_default="0", nullable=False),
        sa.Column("net_fee", _MONEY, nullable=False),
        sa.Column("opening_dues", _MONEY, server_default="0", nullable=False),
        sa.Column("status", sa.Text(), server_default="pending", nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["academic_year_id"], ["academic_years.id"], name=op.f("fk_student_fees_academic_year_id_academic_years"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name=op.f("fk_student_fees_created_by_users"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["fee_structure_id"], ["fee_structures.id"], name=op.f("fk_student_fees_fee_structure_id_fee_structures"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], name=op.f("fk_student_fees_org_id_organizations"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], name=op.f("fk_student_fees_student_id_students"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_student_fees")),
        sa.UniqueConstraint("student_id", "academic_year_id", name=op.f("uq_student_fees_student_id")),
    )
    op.create_index(op.f("ix_student_fees_org_id"), "student_fees", ["org_id"])
    op.create_index(op.f("ix_student_fees_student_id"), "student_fees", ["student_id"])

    op.create_table(
        "installments",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("student_fee_id", sa.UUID(), nullable=False),
        sa.Column("installment_number", sa.Integer(), nullable=False),
        sa.Column("label", sa.Text(), nullable=True),
        sa.Column("amount", _MONEY, nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("paid_amount", _MONEY, server_default="0", nullable=False),
        sa.Column("status", sa.Text(), server_default="pending", nullable=False),
        sa.Column("paid_date", sa.Date(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], name=op.f("fk_installments_org_id_organizations"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_fee_id"], ["student_fees.id"], name=op.f("fk_installments_student_fee_id_student_fees"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_installments")),
    )
    op.create_index(op.f("ix_installments_org_id"), "installments", ["org_id"])
    op.create_index(op.f("ix_installments_student_fee_id"), "installments", ["student_fee_id"])

    op.create_table(
        "fee_transactions",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("student_fee_id", sa.UUID(), nullable=False),
        sa.Column("installment_id", sa.UUID(), nullable=True),
        sa.Column("amount", _MONEY, nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("mode", sa.Text(), nullable=True),
        sa.Column("receipt_number", sa.Text(), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("created_by_name", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name=op.f("fk_fee_transactions_created_by_users"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["installment_id"], ["installments.id"], name=op.f("fk_fee_transactions_installment_id_installments"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], name=op.f("fk_fee_transactions_org_id_organizations"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_fee_id"], ["student_fees.id"], name=op.f("fk_fee_transactions_student_fee_id_student_fees"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_fee_transactions")),
    )
    op.create_index(op.f("ix_fee_transactions_org_id"), "fee_transactions", ["org_id"])
    op.create_index(op.f("ix_fee_transactions_student_fee_id"), "fee_transactions", ["student_fee_id"])

    for stmt in enable_rls_sql(SCHOOL_FEE_TABLES):
        op.execute(stmt)


def downgrade() -> None:
    for stmt in disable_rls_sql(SCHOOL_FEE_TABLES):
        op.execute(stmt)
    for table in ("fee_transactions", "installments", "student_fees",
                  "fee_installment_templates", "fee_structures"):
        op.drop_table(table)
