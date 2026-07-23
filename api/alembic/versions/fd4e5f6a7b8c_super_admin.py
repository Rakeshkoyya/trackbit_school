"""super-admin platform layer

The setup wizard is retired as the school-facing onboarding (founder decision
2026-07-20): schools no longer self-register and self-configure. Instead a
platform operator (the TrackBit dev) creates each school, runs its setup from
the data the school hands over, and only then hands credentials to the school's
admin. `users.is_super_admin` marks that operator: a global user flag (not an
org role) because it lives ABOVE orgs — it grants /platform/* (list every
school, create schools, enter any school as admin). It is granted only by
seed/DB, never by an endpoint.

Revision ID: fd4e5f6a7b8c
Revises: fc3d4e5f6a7b
Create Date: 2026-07-20 09:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "fd4e5f6a7b8c"
down_revision: str | None = "fc3d4e5f6a7b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column(
        "is_super_admin", sa.Boolean(), server_default=sa.text("false"), nullable=False))


def downgrade() -> None:
    op.drop_column("users", "is_super_admin")
