"""Org roles and role-group helpers (SPRD §3.2–3.3).

Extends the seed's admin/member model to the four TrackBit School roles. The
former `member` role maps to `teacher` on migration (P0-B). `admin` keeps every
existing admin semantic (it is the Director).

Hard rules the groups below encode (SPRD §3.3):
  - teachers never see fees        -> fees use OFFICE_UP (admin|office)
  - office never sees academics    -> academics use ACADEMIC (admin|coordinator|teacher)
  - approvals/verify are staff-lead -> COORDINATOR_UP (admin|coordinator)
"""

ADMIN = "admin"  # Director
COORDINATOR = "coordinator"
TEACHER = "teacher"
OFFICE = "office"

ALL_ROLES: tuple[str, ...] = (ADMIN, COORDINATOR, TEACHER, OFFICE)

# Role groups consumed by the permission dependencies (app/core/dependencies.py).
COORDINATOR_UP: frozenset[str] = frozenset({ADMIN, COORDINATOR})
ACADEMIC: frozenset[str] = frozenset({ADMIN, COORDINATOR, TEACHER})
OFFICE_UP: frozenset[str] = frozenset({ADMIN, OFFICE})

# Shared pydantic pattern for role fields on request schemas.
ROLE_PATTERN = "^(admin|coordinator|teacher|office)$"

# SQL fragment for the memberships CHECK constraint (kept in sync with the model).
ROLE_SQL_TUPLE = "('admin', 'coordinator', 'teacher', 'office')"
