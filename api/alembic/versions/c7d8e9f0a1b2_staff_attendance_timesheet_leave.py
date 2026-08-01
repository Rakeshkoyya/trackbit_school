"""staff attendance, timesheet and leave (SF-1)

Founder decision 2026-07-29 — the three things the school could not record:

- staff_attendance_days / staff_absences: admin-marked staff attendance, in the
  capture-by-exception shape the classroom already uses (P1v2). The day row is
  what separates "nobody was absent" from "nobody marked it"; only absentees get
  a row. Present/absent only — no late tier for staff (founder call).
- timesheet_entries: what a teacher does with a period they are NOT teaching.
  Teaching periods stay in timetable_slots and are never copied here — one
  source of truth per period.
- leave_requests + leave_request_events: append-only decision history (law 3, the
  plan_approvals / demo_request_notes shape); leave_requests.status is a derived
  cache of the newest event.
- organizations.leaves_per_year / leaves_per_month: the school's leave policy,
  configurable in Setup → Settings.

Revision ID: c7d8e9f0a1b2
Revises: d5e6f7a8b9c0
Create Date: 2026-07-29 10:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.rls import SCHOOL_STAFF_TABLES, disable_rls_sql, enable_rls_sql

revision: str = "c7d8e9f0a1b2"
down_revision: str | None = "d5e6f7a8b9c0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── leave policy on the org ──────────────────────────────────────────────
    op.add_column(
        "organizations",
        sa.Column("leaves_per_year", sa.Integer(), server_default="8", nullable=False),
    )
    op.add_column(
        "organizations",
        sa.Column("leaves_per_month", sa.Integer(), server_default="1", nullable=False),
    )
    op.create_check_constraint(
        op.f("ck_organizations_leave_policy_valid"), "organizations",
        "leaves_per_year >= 0 AND leaves_per_month >= 0",
    )

    # ── staff attendance (day + absence exceptions) ──────────────────────────
    op.create_table(
        "staff_attendance_days",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("marked_by_member_id", sa.UUID(), nullable=True),
        sa.Column("marked_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"],
                                name=op.f("fk_staff_attendance_days_org_id_organizations"),
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["marked_by_member_id"], ["memberships.id"],
            name=op.f("fk_staff_attendance_days_marked_by_member_id_memberships"),
            ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_staff_attendance_days")),
        sa.UniqueConstraint("org_id", "date", name="uq_staff_attendance_days_org_date"),
    )
    op.create_index(op.f("ix_staff_attendance_days_org_id"), "staff_attendance_days", ["org_id"])

    op.create_table(
        "staff_absences",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("day_id", sa.UUID(), nullable=False),
        sa.Column("member_id", sa.UUID(), nullable=False),
        sa.Column("source", sa.Text(), server_default="manual", nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.CheckConstraint("source IN ('manual', 'leave')",
                           name=op.f("ck_staff_absences_staff_absence_source_valid")),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"],
                                name=op.f("fk_staff_absences_org_id_organizations"),
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["day_id"], ["staff_attendance_days.id"],
                                name=op.f("fk_staff_absences_day_id_staff_attendance_days"),
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["member_id"], ["memberships.id"],
                                name=op.f("fk_staff_absences_member_id_memberships"),
                                ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_staff_absences")),
        sa.UniqueConstraint("day_id", "member_id", name="uq_staff_absences_day_member"),
    )
    op.create_index(op.f("ix_staff_absences_org_id"), "staff_absences", ["org_id"])
    op.create_index(op.f("ix_staff_absences_day_id"), "staff_absences", ["day_id"])
    op.create_index(op.f("ix_staff_absences_member_id"), "staff_absences", ["member_id"])

    # ── timesheet ────────────────────────────────────────────────────────────
    op.create_table(
        "timesheet_entries",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("member_id", sa.UUID(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("period_no", sa.Integer(), nullable=False),
        sa.Column("work_type", sa.Text(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("period_no >= 1",
                           name=op.f("ck_timesheet_entries_timesheet_period_no_valid")),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"],
                                name=op.f("fk_timesheet_entries_org_id_organizations"),
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["member_id"], ["memberships.id"],
                                name=op.f("fk_timesheet_entries_member_id_memberships"),
                                ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_timesheet_entries")),
        sa.UniqueConstraint("org_id", "member_id", "date", "period_no",
                            name="uq_timesheet_entries_member_date_period"),
    )
    op.create_index(op.f("ix_timesheet_entries_org_id"), "timesheet_entries", ["org_id"])
    op.create_index(op.f("ix_timesheet_entries_member_id"), "timesheet_entries", ["member_id"])
    op.create_index("ix_timesheet_entries_org_date", "timesheet_entries", ["org_id", "date"])

    # ── leave ────────────────────────────────────────────────────────────────
    op.create_table(
        "leave_requests",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("member_id", sa.UUID(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("days", sa.Integer(), server_default="1", nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default="pending", nullable=False),
        sa.CheckConstraint("end_date >= start_date",
                           name=op.f("ck_leave_requests_leave_dates_valid")),
        sa.CheckConstraint("status IN ('pending', 'approved', 'rejected', 'cancelled')",
                           name=op.f("ck_leave_requests_leave_status_valid")),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"],
                                name=op.f("fk_leave_requests_org_id_organizations"),
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["member_id"], ["memberships.id"],
                                name=op.f("fk_leave_requests_member_id_memberships"),
                                ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_leave_requests")),
    )
    op.create_index(op.f("ix_leave_requests_org_id"), "leave_requests", ["org_id"])
    op.create_index(op.f("ix_leave_requests_member_id"), "leave_requests", ["member_id"])
    op.create_index("ix_leave_requests_org_status", "leave_requests", ["org_id", "status"])

    op.create_table(
        "leave_request_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("request_id", sa.UUID(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("actor_member_id", sa.UUID(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("action IN ('applied', 'approved', 'rejected', 'cancelled')",
                           name=op.f("ck_leave_request_events_leave_event_action_valid")),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"],
                                name=op.f("fk_leave_request_events_org_id_organizations"),
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["request_id"], ["leave_requests.id"],
                                name=op.f("fk_leave_request_events_request_id_leave_requests"),
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_member_id"], ["memberships.id"],
                                name=op.f("fk_leave_request_events_actor_member_id_memberships"),
                                ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_leave_request_events")),
    )
    op.create_index(op.f("ix_leave_request_events_org_id"), "leave_request_events", ["org_id"])
    op.create_index(op.f("ix_leave_request_events_request_id"), "leave_request_events",
                    ["request_id"])

    # Law 2: every new org-scoped table carries the org_isolation policy.
    for stmt in enable_rls_sql(SCHOOL_STAFF_TABLES):
        op.execute(stmt)


def downgrade() -> None:
    for stmt in disable_rls_sql(SCHOOL_STAFF_TABLES):
        op.execute(stmt)
    op.drop_table("leave_request_events")
    op.drop_table("leave_requests")
    op.drop_table("timesheet_entries")
    op.drop_table("staff_absences")
    op.drop_table("staff_attendance_days")
    op.drop_constraint(op.f("ck_organizations_leave_policy_valid"), "organizations",
                       type_="check")
    op.drop_column("organizations", "leaves_per_month")
    op.drop_column("organizations", "leaves_per_year")
