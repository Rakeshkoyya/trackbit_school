"""V1-2 — setup, onboarding & handover.

organizations gains:
  - school_code (D-13/S-57): random, unique, unguessable — the parent's way into
    their school at login. Backfilled for every existing org.
  - address / state / board (§6 ①): collected at school creation; state + board
    are what scope the V1-7 observance catalogue.
  - attendance_mode (D-01): every_period | first_period | twice_daily.
  - min_attendance_pct / homework_gap_days: thresholds V1-3 / V1-5 consume.
  - work_categories (D-19/S-69): [{key,label,active}] — stable keys, mutable
    labels, retire never delete. NULL = the code defaults.
  - handed_over_at (§6 ⑤): the operator marked the school handed over.

students.date_of_birth (D-13): the parent's password + the birthday feed. The
importer parses it tolerantly and never guesses; the readiness report counts
the gap.

memberships.date_of_birth: staff birthdays (D-56 feed).

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-08-01
"""

import secrets

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "f2a3b4c5d6e7"
down_revision = "e1f2a3b4c5d6"
branch_labels = None
depends_on = None

# Mirrors core/school_code.py (no 0/O · 1/I/L). Inlined so the migration stays
# runnable even if the helper moves.
_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"


def _code() -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(7))


def upgrade() -> None:
    op.add_column("organizations", sa.Column("school_code", sa.Text(), nullable=True))
    op.add_column("organizations", sa.Column("address", sa.Text(), nullable=True))
    op.add_column("organizations", sa.Column("state", sa.Text(), nullable=True))
    op.add_column("organizations", sa.Column("board", sa.Text(), nullable=True))
    op.add_column("organizations", sa.Column(
        "attendance_mode", sa.Text(), nullable=False, server_default="every_period"))
    op.add_column("organizations", sa.Column(
        "min_attendance_pct", sa.Integer(), nullable=False, server_default="75"))
    op.add_column("organizations", sa.Column(
        "homework_gap_days", sa.Integer(), nullable=False, server_default="3"))
    op.add_column("organizations", sa.Column("work_categories", JSONB(), nullable=True))
    op.add_column("organizations", sa.Column(
        "handed_over_at", sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint(
        "attendance_mode_valid", "organizations",
        "attendance_mode IN ('every_period', 'first_period', 'twice_daily')")
    op.create_check_constraint(
        "min_attendance_pct_valid", "organizations",
        "min_attendance_pct >= 0 AND min_attendance_pct <= 100")
    op.create_check_constraint(
        "homework_gap_days_valid", "organizations", "homework_gap_days >= 1")

    # Backfill: every existing org gets a code, then the unique constraint lands.
    conn = op.get_bind()
    taken = {c for (c,) in conn.execute(
        sa.text("SELECT school_code FROM organizations WHERE school_code IS NOT NULL"))}
    for (org_id,) in conn.execute(
            sa.text("SELECT id FROM organizations WHERE school_code IS NULL")).fetchall():
        code = _code()
        while code in taken:
            code = _code()
        taken.add(code)
        conn.execute(sa.text(
            "UPDATE organizations SET school_code = :c WHERE id = :i"),
            {"c": code, "i": org_id})
    op.create_unique_constraint(
        "uq_organizations_school_code", "organizations", ["school_code"])

    op.add_column("students", sa.Column("date_of_birth", sa.Date(), nullable=True))
    op.add_column("memberships", sa.Column("date_of_birth", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("memberships", "date_of_birth")
    op.drop_column("students", "date_of_birth")
    op.drop_constraint("uq_organizations_school_code", "organizations")
    op.drop_constraint("homework_gap_days_valid", "organizations")
    op.drop_constraint("min_attendance_pct_valid", "organizations")
    op.drop_constraint("attendance_mode_valid", "organizations")
    for col in ("handed_over_at", "work_categories", "homework_gap_days",
                "min_attendance_pct", "attendance_mode", "board", "state",
                "address", "school_code"):
        op.drop_column("organizations", col)
