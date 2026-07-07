"""Org roles and role-group helpers (SPRD v2 §2; supersedes v1 §3.2–3.3).

v2 collapses the four school roles to two:
  * `admin`   — runs the school: setup, plan approval, bands, fees, dashboard,
                members. Whoever registers the org is an admin and can add more.
  * `teacher` — all academic staff (subject teachers, wardens, coordinators in
                spirit): My Day capture, sessions, homework, viewing plans.

Former `coordinator` and `office` memberships were migrated to `admin`
(migration e9fab0c1d2e3_two_roles).

The v1 group names are kept so permission dependencies and services don't
churn; their v2 meanings:
  - COORDINATOR_UP -> admin only          (approvals, verification, compliance)
  - OFFICE_UP      -> admin only          (fees; teachers never see fees)
  - ACADEMIC       -> admin | teacher     (every member is academic staff in v2)
"""

ADMIN = "admin"
TEACHER = "teacher"

ALL_ROLES: tuple[str, ...] = (ADMIN, TEACHER)

# Role groups consumed by the permission dependencies (app/core/dependencies.py).
COORDINATOR_UP: frozenset[str] = frozenset({ADMIN})
ACADEMIC: frozenset[str] = frozenset({ADMIN, TEACHER})
OFFICE_UP: frozenset[str] = frozenset({ADMIN})

# Shared pydantic pattern for role fields on request schemas.
ROLE_PATTERN = "^(admin|teacher)$"

# SQL fragment for the memberships CHECK constraint (kept in sync with the model).
ROLE_SQL_TUPLE = "('admin', 'teacher')"
