"""school master data: years/terms/classes/subjects/students/guardians (SPRD §4.2)

Revision ID: d2e3f4a5b6c7
Revises: d1e2f3a4b5c6
Create Date: 2026-07-07 11:30:00.000000

The shared spine under both academics and fees. All tables carry org_id and get
the org_isolation RLS policy (engaged via app.core.rls.enable_rls_sql).
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.rls import SCHOOL_MASTER_TABLES, disable_rls_sql, enable_rls_sql

revision: str = "d2e3f4a5b6c7"
down_revision: str | None = "d1e2f3a4b5c6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "academic_years",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], name=op.f("fk_academic_years_org_id_organizations"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_academic_years")),
        sa.UniqueConstraint("org_id", "label", name=op.f("uq_academic_years_org_id")),
    )
    op.create_index(op.f("ix_academic_years_org_id"), "academic_years", ["org_id"])

    op.create_table(
        "student_categories",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], name=op.f("fk_student_categories_org_id_organizations"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_student_categories")),
        sa.UniqueConstraint("org_id", "name", name=op.f("uq_student_categories_org_id")),
    )
    op.create_index(op.f("ix_student_categories_org_id"), "student_categories", ["org_id"])

    op.create_table(
        "subjects",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], name=op.f("fk_subjects_org_id_organizations"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_subjects")),
        sa.UniqueConstraint("org_id", "name", name=op.f("uq_subjects_org_id")),
    )
    op.create_index(op.f("ix_subjects_org_id"), "subjects", ["org_id"])

    op.create_table(
        "terms",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("academic_year_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["academic_year_id"], ["academic_years.id"], name=op.f("fk_terms_academic_year_id_academic_years"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], name=op.f("fk_terms_org_id_organizations"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_terms")),
    )
    op.create_index(op.f("ix_terms_org_id"), "terms", ["org_id"])

    op.create_table(
        "school_classes",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("academic_year_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("section", sa.Text(), nullable=True),
        sa.Column("class_teacher_member_id", sa.UUID(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["academic_year_id"], ["academic_years.id"], name=op.f("fk_school_classes_academic_year_id_academic_years"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["class_teacher_member_id"], ["memberships.id"], name=op.f("fk_school_classes_class_teacher_member_id_memberships"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], name=op.f("fk_school_classes_org_id_organizations"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_school_classes")),
        sa.UniqueConstraint("org_id", "academic_year_id", "name", "section", name=op.f("uq_school_classes_org_id")),
    )
    op.create_index(op.f("ix_school_classes_org_id"), "school_classes", ["org_id"])

    op.create_table(
        "class_subjects",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("class_id", sa.UUID(), nullable=False),
        sa.Column("subject_id", sa.UUID(), nullable=False),
        sa.Column("teacher_member_id", sa.UUID(), nullable=True),
        sa.Column("periods_per_week", sa.Integer(), server_default="0", nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["class_id"], ["school_classes.id"], name=op.f("fk_class_subjects_class_id_school_classes"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], name=op.f("fk_class_subjects_org_id_organizations"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], name=op.f("fk_class_subjects_subject_id_subjects"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["teacher_member_id"], ["memberships.id"], name=op.f("fk_class_subjects_teacher_member_id_memberships"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_class_subjects")),
        sa.UniqueConstraint("class_id", "subject_id", name=op.f("uq_class_subjects_class_id")),
    )
    op.create_index(op.f("ix_class_subjects_org_id"), "class_subjects", ["org_id"])

    op.create_table(
        "students",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("admission_no", sa.Text(), nullable=False),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("class_id", sa.UUID(), nullable=True),
        sa.Column("roll_no", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), server_default="active", nullable=False),
        sa.Column("category_id", sa.UUID(), nullable=True),
        sa.Column("photo", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("status IN ('active', 'left')", name=op.f("ck_students_status_valid")),
        sa.ForeignKeyConstraint(["category_id"], ["student_categories.id"], name=op.f("fk_students_category_id_student_categories"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["class_id"], ["school_classes.id"], name=op.f("fk_students_class_id_school_classes"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], name=op.f("fk_students_org_id_organizations"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_students")),
        sa.UniqueConstraint("org_id", "admission_no", name=op.f("uq_students_org_id")),
    )
    op.create_index(op.f("ix_students_org_id"), "students", ["org_id"])

    op.create_table(
        "guardians",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("student_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("relation", sa.Text(), nullable=True),
        sa.Column("phone", sa.Text(), nullable=False),
        sa.Column("is_primary", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("notify_opt_out", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], name=op.f("fk_guardians_org_id_organizations"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], name=op.f("fk_guardians_student_id_students"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_guardians")),
    )
    op.create_index(op.f("ix_guardians_org_id"), "guardians", ["org_id"])

    # Engage the org_isolation RLS safety net for exactly these new tables.
    for stmt in enable_rls_sql(SCHOOL_MASTER_TABLES):
        op.execute(stmt)


def downgrade() -> None:
    for stmt in disable_rls_sql(SCHOOL_MASTER_TABLES):
        op.execute(stmt)
    for table in ("guardians", "students", "class_subjects", "school_classes",
                  "terms", "subjects", "student_categories", "academic_years"):
        op.drop_table(table)
