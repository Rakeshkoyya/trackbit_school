"""school roles: member -> teacher, add coordinator/office (SPRD §3.2)

Revision ID: d1e2f3a4b5c6
Revises: c9d0e1f2a3b4
Create Date: 2026-07-07 11:00:00.000000

Extends memberships.org_role from ('admin','member') to
('admin','coordinator','teacher','office'). Existing members become teachers.
"""
from collections.abc import Sequence

from alembic import op


revision: str = "d1e2f3a4b5c6"
down_revision: str | None = "c9d0e1f2a3b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Bare constraint token — alembic re-applies the ck_%(table)s_ naming convention,
# so passing the full name would double-prefix it (ck_memberships_ck_memberships_…).
_CK = "org_role_valid"


def upgrade() -> None:
    # Drop the old domain check, remap data, then install the new domain check.
    op.drop_constraint(_CK, "memberships", type_="check")
    op.execute("UPDATE memberships SET org_role = 'teacher' WHERE org_role = 'member'")
    op.create_check_constraint(
        "org_role_valid",
        "memberships",
        "org_role IN ('admin', 'coordinator', 'teacher', 'office')",
    )


def downgrade() -> None:
    op.drop_constraint(_CK, "memberships", type_="check")
    # Collapse the wider role set back into the old two-value domain (lossy).
    op.execute("UPDATE memberships SET org_role = 'member' WHERE org_role <> 'admin'")
    op.create_check_constraint(
        "org_role_valid",
        "memberships",
        "org_role IN ('admin', 'member')",
    )
