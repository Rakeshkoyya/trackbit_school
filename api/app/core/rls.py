"""Row-Level Security policies — the org-isolation safety net (plan §4, B-law).

App-layer query scoping (org_id from auth context) is the PRIMARY guard. RLS is
defence in depth: if a query ever forgets its org filter, the database still
refuses to leak across tenants — but ONLY once the connection has opted in by
setting `app.current_org_id`.

Policy semantics per table with an org_id column:
    - GUC unset/empty  -> full access (today's default; app scoping is the guard)
    - GUC set          -> rows are visible only when org_id matches

This lets us roll RLS out without breaking unscoped/admin paths, and engage it
per-request once auth resolves org context (wired in P0-BE-03).

`FORCE ROW LEVEL SECURITY` makes the policy apply to the table owner too (the
migration role), so the safety net is real and testable.
"""

# Tables that carry a non-null org_id and represent tenant business data.
#
# IMPORTANT: the initial migration reads this tuple *live* when it enables RLS,
# so it must only ever list tables that exist by the end of that migration (the
# seed's task-module tables). New modules add their own org-scoped tables and
# engage RLS for them in their OWN migration via `enable_rls_sql([...])` — do NOT
# append to this tuple, or a fresh `alembic upgrade` would try to enable RLS on
# tables that don't exist yet. `SCHOOL_MASTER_TABLES` below documents P0-C's set.
ORG_SCOPED_TABLES = (
    "memberships",
    "boards",
    "task_templates",
    "task_instances",
    "task_events",
    "notifications",
)

# P0-C master data (SPRD §4.2) — engaged in migration d2e3f4a5b6c7.
SCHOOL_MASTER_TABLES = (
    "academic_years",
    "terms",
    "student_categories",
    "subjects",
    "school_classes",
    "class_subjects",
    "students",
    "guardians",
)

# P0-D fee port (SPRD §4.6) — engaged in migration d3f4a5b6c7d8.
SCHOOL_FEE_TABLES = (
    "fee_structures",
    "fee_installment_templates",
    "student_fees",
    "installments",
    "fee_transactions",
)

# P1 academic capture (SPRD §4.3–4.4) — engaged as each migration lands.
SCHOOL_PLANNER_TABLES = (
    "calendar_events",
)

# P1-B/C syllabus + plan (SPRD §4.3) — engaged in migration d5b6c7d8e9fa.
SCHOOL_SYLLABUS_TABLES = (
    "syllabus_units",
    "syllabus_topics",
    "plans",
    "plan_entries",
)

# V2-P11 term-scoped planning — engaged in migration f7c8d9e0f1a2.
SCHOOL_PLAN_APPROVAL_TABLES = (
    "plan_approvals",
)

# P1-D/E classroom capture (SPRD §4.4) — engaged in migration d6c7d8e9fab0.
SCHOOL_CLASSROOM_TABLES = (
    "lesson_logs",
    "homework_assignments",
    "homework_checks",
)

# Teacher-view deep log (2026-07) — engaged in migration a8b9c0d1e2f3.
SCHOOL_OBSERVATION_TABLES = (
    "lesson_observations",
)

# P1.5 sessions (SPRD §4.4) — engaged in migration d7d8e9fab0c1.
SCHOOL_SESSION_TABLES = (
    "sessions",
    "session_students",
    "session_meetings",
    "session_attendance",
)

# HS-1 hostel sessions — engaged in migration f8d9e0f1a2b3.
SCHOOL_HOSTEL_TABLES = (
    "session_classes",
    "session_media",
    "session_student_logs",
)

# V2-P1 timetable (SPRD2 §4, §5.3) — engaged in migration f0a1b2c3d4e5.
SCHOOL_TIMETABLE_TABLES = (
    "timetable_slots",
)

# V2-P2 attendance (SPRD2 §4.4, §5.4) — engaged in migration f1b2c3d4e5f6.
# V2-P6 renamed `attendance_marks` → `class_periods` (migration f5a6b7c8d9e0). The
# rename preserves the table OID, so its RLS policy and grants carry over; the
# migration re-runs enable_rls_sql on the new name anyway (idempotent).
SCHOOL_ATTENDANCE_TABLES = (
    "class_periods",
    "attendance_exceptions",
)

# V2-P7 exam portions (SPRD2 §5.2) — engaged in migration f6b7c8d9e0f1.
SCHOOL_EXAM_TABLES = (
    "exam_portions",
)

# V2-P3 daily checks / recommendations (SPRD2 §4.4, §5.5) — engaged in f2c3d4e5f6a7.
SCHOOL_CHECKS_TABLES = (
    "daily_checks",
    "check_results",
)

# V2-P4 daily report (SPRD2 §4.4, §5.6) — engaged in migration f3d4e5f6a7b8.
SCHOOL_REPORT_TABLES = (
    "daily_reports",
)

# V2-P5 wizard + plan comments (SPRD2 §4.4, §5.1/§5.2) — engaged in f4e5f6a7b8c9.
SCHOOL_WIZARD_TABLES = (
    "onboarding_state",
    "plan_comments",
)

# SC-1 photo score capture — engaged in migration fae1f2a3b4c5.
SCHOOL_CAPTURE_TABLES = (
    "score_captures",
    "score_capture_pages",
)

# P3 assessments & bands (SPRD §4.5) — engaged in migration d8e9fab0c1d2.
SCHOOL_ASSESSMENT_TABLES = (
    "skill_areas",
    "assessment_cycles",
    "assessment_scores",
    "student_bands",
    "interventions",
    "intervention_items",
)

# NULLIF guards the ::uuid cast: Postgres does NOT guarantee OR short-circuit
# evaluation, so the cast can run even when an earlier branch is true. NULLIF
# turns '' into NULL, and NULL::uuid is valid (NULL) — so the cast never errors,
# whatever order the planner picks. When the GUC is unset/empty the row passes
# via the first two branches; app-layer scoping remains the primary guard.
_USING = (
    "current_setting('app.current_org_id', true) IS NULL "
    "OR current_setting('app.current_org_id', true) = '' "
    "OR org_id = NULLIF(current_setting('app.current_org_id', true), '')::uuid"
)


def create_policies_sql(tables: "tuple[str, ...] | list[str] | None" = None) -> list[str]:
    """(Re)create the org_isolation policy on each table (idempotent via DROP IF EXISTS)."""
    stmts: list[str] = []
    for table in ORG_SCOPED_TABLES if tables is None else tables:
        stmts.append(f"DROP POLICY IF EXISTS org_isolation ON {table};")
        stmts.append(
            f"CREATE POLICY org_isolation ON {table} "
            f"USING ({_USING}) WITH CHECK ({_USING});"
        )
    return stmts


def enable_rls_sql(tables: "tuple[str, ...] | list[str] | None" = None) -> list[str]:
    """Enable + force RLS and (re)create the org_isolation policy on `tables`.

    Pass an explicit list from a module's migration to engage RLS for that
    module's new tables. Defaults to the seed's ORG_SCOPED_TABLES."""
    target = ORG_SCOPED_TABLES if tables is None else tables
    stmts: list[str] = []
    for table in target:
        stmts.append(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
        stmts.append(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")
    stmts.extend(create_policies_sql(target))
    return stmts


def disable_rls_sql(tables: "tuple[str, ...] | list[str] | None" = None) -> list[str]:
    target = ORG_SCOPED_TABLES if tables is None else tables
    stmts: list[str] = []
    for table in target:
        stmts.append(f"DROP POLICY IF EXISTS org_isolation ON {table};")
        stmts.append(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;")
        stmts.append(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")
    return stmts


# Back-compat aliases used by the initial migration (operate on ORG_SCOPED_TABLES).
def upgrade_sql() -> list[str]:
    return enable_rls_sql()


def downgrade_sql() -> list[str]:
    return disable_rls_sql()
