"""School codes (D-13, S-57) — how a parent finds their school at login.

Random, 6–8 chars, from an alphabet with no lookalikes (no 0/O, 1/I/L), because
the code is read out over the phone and typed by parents. NEVER derived from the
school's name: `DPS2024` plus a browsable class list is the whole school's
roster; a random code removes the drive-by case entirely (S-57).
"""

import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

# 29 chars, no 0/O · 1/I/L lookalikes. 7 chars ≈ 2^34 — unguessable in practice.
_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"


def generate_school_code(length: int = 7) -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(length))


def new_school_code(db: Session) -> str:
    """A code no other org holds. Collision is ~impossible; the loop is a guard,
    not a strategy."""
    from app.models import Organization  # noqa: PLC0415 — avoid model import cycle

    for _ in range(20):
        code = generate_school_code()
        if db.scalar(select(Organization.id).where(
                Organization.school_code == code)) is None:
            return code
    raise RuntimeError("Could not generate a unique school code.")
