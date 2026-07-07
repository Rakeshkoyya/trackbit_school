"""v2 roles: collapse coordinator/office into admin (SPRD v2 §2)

Revision ID: e9fab0c1d2e3
Revises: d8e9fab0c1d2
Create Date: 2026-07-07 18:00:00.000000

The founder's v2 redesign keeps two roles only: `admin` (runs the school) and
`teacher` (all academic staff). Former coordinators and office staff become
admins — they were school-management people in both cases.
"""
from collections.abc import Sequence

from alembic import op


revision: str = "e9fab0c1d2e3"
down_revision: str | None = "d8e9fab0c1d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Bare constraint token — alembic re-applies the ck_%(table)s_ naming convention,
# so passing the full name would double-prefix it (see d1e2f3a4b5c6).
_CK = "org_role_valid"


def upgrade() -> None:
    op.drop_constraint(_CK, "memberships", type_="check")
    op.execute("UPDATE memberships SET org_role = 'admin' WHERE org_role IN ('coordinator', 'office')")
    op.create_check_constraint(
        "org_role_valid",
        "memberships",
        "org_role IN ('admin', 'teacher')",
    )


def downgrade() -> None:
    # Lossy: we cannot tell which admins were coordinators/office before.
    op.drop_constraint(_CK, "memberships", type_="check")
    op.create_check_constraint(
        "org_role_valid",
        "memberships",
        "org_role IN ('admin', 'coordinator', 'teacher', 'office')",
    )
