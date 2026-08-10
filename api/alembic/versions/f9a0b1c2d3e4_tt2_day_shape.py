"""TT-2 — the day shape: effective-dated bell schedules, typed timetable slots

`D-112`…`D-115`. Three things the old model could not say:

1. **When the day happens, over time.** Timings were one JSONB on
   `academic_years`, so restructuring the day after the Term 1 exams re-rendered
   September's timesheets with October's clock. `bell_schedules` is effective-
   dated exactly like `timetable_slots`, and for the same reason (Law 3).
2. **A period that is not a subject.** `timetable_slots.class_subject_id` was NOT
   NULL, so homework class, sports, assembly and extra courses could not be
   scheduled at all. It becomes nullable beside a `session_id`, with a CHECK that
   a cell holds exactly one of the two.
3. **More than one teacher on a block.** `session_staff` — assembly and yoga are
   taken by whoever is free, and before this only the single owner could capture
   anything.

Ordering note: this is additive except for two relaxations (`class_subject_id`
NOT NULL → NULL, and the `kind` CHECK widening). Both only ever *accept more*, so
production may migrate before the code that writes blocks deploys — which is the
required order here.

The kind list and the slot types are spelled out literally rather than imported
from `core/day_shape`. A migration is a historical artifact: it must keep meaning
what it meant the day it ran, even after that module grows a seventh kind.

Revision ID: f9a0b1c2d3e4
Revises: e8f9a0b1c2d3
Create Date: 2026-08-10
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.core.rls import disable_rls_sql, enable_rls_sql

revision = "f9a0b1c2d3e4"
down_revision = "e8f9a0b1c2d3"
branch_labels = None
depends_on = None

_RLS_TABLES = ["bell_schedules", "session_staff"]

_KINDS_OLD = "'study', 'homework', 'activity'"
_KINDS_NEW = "'study', 'homework', 'activity', 'sports', 'course', 'assembly'"

# A cell holds exactly one payload. Written as one constraint rather than two
# nullable columns and a prayer: with both ids settable, the grid renderer and
# the My Day feed would each pick one and quietly disagree.
_SLOT_PAYLOAD = (
    "(slot_type = 'subject' AND class_subject_id IS NOT NULL AND session_id IS NULL)"
    " OR (slot_type = 'block' AND session_id IS NOT NULL AND class_subject_id IS NULL)"
)


def _swap_kind_check(kinds: str) -> None:
    """Replace `sessions`' kind CHECK, whatever it is currently called.

    HS-1 created it as `op.create_check_constraint("ck_sessions_kind_valid", …)`
    — a name that already carried the prefix — so the metadata naming convention
    prefixed it a second time and every database has it as
    `ck_sessions_ck_sessions_kind_valid`. `op.drop_constraint("kind_valid", …)`
    resolves to the single-prefixed name and finds nothing. Dropping both
    candidates by raw SQL with IF EXISTS is the only form that works on a
    database at either name, which matters because this has to run unattended
    against production.
    """
    op.execute("ALTER TABLE sessions DROP CONSTRAINT IF EXISTS "
               "ck_sessions_ck_sessions_kind_valid")
    op.execute("ALTER TABLE sessions DROP CONSTRAINT IF EXISTS ck_sessions_kind_valid")
    op.execute(f"ALTER TABLE sessions ADD CONSTRAINT ck_sessions_kind_valid "
               f"CHECK (kind IN ({kinds}))")


def upgrade() -> None:
    # ── 1. bell_schedules ────────────────────────────────────────────────────
    op.create_table(
        "bell_schedules",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("academic_year_id", sa.UUID(), nullable=False),
        sa.Column("periods_per_day", sa.Integer(), server_default="8", nullable=False),
        sa.Column("entries", postgresql.JSONB(astext_type=sa.Text()),
                  server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["academic_year_id"], ["academic_years.id"], ondelete="CASCADE"),
        sa.CheckConstraint("periods_per_day >= 0 AND periods_per_day <= 16",
                           name="bell_periods_per_day_valid"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_bell_schedules_org_id", "bell_schedules", ["org_id"])
    op.create_index("ix_bell_schedules_academic_year_id", "bell_schedules",
                    ["academic_year_id"])
    op.create_index("ix_bell_schedules_year_current", "bell_schedules",
                    ["academic_year_id", "effective_to"])

    # Backfill: every existing year keeps the exact day it already had, valid
    # from the day it started tracking. Without this, every school's timesheet
    # and day-book would go blank the moment the readers switch over.
    op.execute(
        """
        INSERT INTO bell_schedules
            (id, org_id, academic_year_id, periods_per_day, entries, note,
             effective_from, effective_to, created_at)
        SELECT gen_random_uuid(), y.org_id, y.id,
               COALESCE(y.periods_per_day, 8),
               COALESCE(y.period_times, '[]'::jsonb),
               'Carried over from the year''s original timings',
               COALESCE(y.tracking_start_date, y.start_date, CURRENT_DATE),
               NULL, now()
        FROM academic_years y
        """
    )

    # ── 2. typed timetable slots ─────────────────────────────────────────────
    op.add_column("timetable_slots",
                  sa.Column("slot_type", sa.Text(), server_default="subject", nullable=False))
    op.add_column("timetable_slots", sa.Column("session_id", sa.UUID(), nullable=True))
    op.create_foreign_key("fk_timetable_slots_session_id", "timetable_slots", "sessions",
                          ["session_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_timetable_slots_session_id", "timetable_slots", ["session_id"])
    op.alter_column("timetable_slots", "class_subject_id", existing_type=sa.UUID(),
                    nullable=True)
    # Every pre-TT-2 row is a subject with class_subject_id set, so the CHECK is
    # satisfied by the existing data and needs no repair pass.
    op.create_check_constraint("slot_payload_valid", "timetable_slots", _SLOT_PAYLOAD)

    # ── 3. sessions: more kinds, more staff, a class log ─────────────────────
    _swap_kind_check(_KINDS_NEW)

    op.create_table(
        "session_staff",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column("member_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["member_id"], ["memberships.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "member_id", name="uq_session_staff_session_id"),
    )
    op.create_index("ix_session_staff_org_id", "session_staff", ["org_id"])
    op.create_index("ix_session_staff_session_id", "session_staff", ["session_id"])

    op.add_column("session_meetings", sa.Column("note", sa.Text(), nullable=True))
    op.add_column("session_meetings", sa.Column("taken_by_member_id", sa.UUID(), nullable=True))
    op.create_foreign_key("fk_session_meetings_taken_by", "session_meetings", "memberships",
                          ["taken_by_member_id"], ["id"], ondelete="SET NULL")

    # ── 4. law 2 ─────────────────────────────────────────────────────────────
    for stmt in enable_rls_sql(_RLS_TABLES):
        op.execute(stmt)


def downgrade() -> None:
    for stmt in disable_rls_sql(_RLS_TABLES):
        op.execute(stmt)

    op.drop_constraint("fk_session_meetings_taken_by", "session_meetings", type_="foreignkey")
    op.drop_column("session_meetings", "taken_by_member_id")
    op.drop_column("session_meetings", "note")
    op.drop_index("ix_session_staff_session_id", table_name="session_staff")
    op.drop_index("ix_session_staff_org_id", table_name="session_staff")
    op.drop_table("session_staff")

    # Blocks cannot survive the narrowing — their kinds and their slots both go.
    op.execute(f"DELETE FROM sessions WHERE kind NOT IN ({_KINDS_OLD})")
    _swap_kind_check(_KINDS_OLD)

    op.drop_constraint("slot_payload_valid", "timetable_slots", type_="check")
    op.execute("DELETE FROM timetable_slots WHERE slot_type <> 'subject'")
    op.alter_column("timetable_slots", "class_subject_id", existing_type=sa.UUID(),
                    nullable=False)
    op.drop_index("ix_timetable_slots_session_id", table_name="timetable_slots")
    op.drop_constraint("fk_timetable_slots_session_id", "timetable_slots", type_="foreignkey")
    op.drop_column("timetable_slots", "session_id")
    op.drop_column("timetable_slots", "slot_type")

    op.drop_index("ix_bell_schedules_year_current", table_name="bell_schedules")
    op.drop_index("ix_bell_schedules_academic_year_id", table_name="bell_schedules")
    op.drop_index("ix_bell_schedules_org_id", table_name="bell_schedules")
    op.drop_table("bell_schedules")
