"""Combined periods — two or more classes taught as one meeting (TT-4).

A school with a small 5th and a small 6th runs them together for Maths: one
teacher, one room, one lesson. Said on the grid that is Maths in both classes at
period 1 with one teacher — which is exactly what the clash validator exists to
catch, and from the grid alone it cannot tell the arrangement from the mistake.
So the arrangement gets said out loud.

The table is almost empty on purpose. **Membership is the set of live
`timetable_slots` pointing at it**, so weekday, period, classes and subjects are
never copied here — a combination that cached its own weekday would keep it
after somebody moved the period, and the two stores would disagree about when
the lesson happens. It also means membership inherits the grid's effective-dating
for free: combining and un-combining close slot rows and open new ones like any
other cell edit (Law 3).

Additive: the column is nullable with no default, so prod can take this ahead of
the code deploy as the convention requires.

Revision ID: b6c7d8e9f0a1
Revises: a5b6c7d8e9f0
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.core.rls import SCHOOL_COMBINED_TABLES, disable_rls_sql, enable_rls_sql

revision: str = "b6c7d8e9f0a1"
down_revision: str | None = "a5b6c7d8e9f0"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "combined_periods",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["org_id"], ["organizations.id"],
            name=op.f("fk_combined_periods_org_id_organizations"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_combined_periods")),
    )
    op.create_index(op.f("ix_combined_periods_org_id"), "combined_periods", ["org_id"])

    op.add_column(
        "timetable_slots",
        sa.Column("combined_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_timetable_slots_combined_id_combined_periods"),
        "timetable_slots", "combined_periods", ["combined_id"], ["id"],
        ondelete="SET NULL",
    )
    op.create_index(op.f("ix_timetable_slots_combined_id"), "timetable_slots",
                    ["combined_id"])

    for stmt in enable_rls_sql(SCHOOL_COMBINED_TABLES):
        op.execute(stmt)


def downgrade() -> None:
    for stmt in disable_rls_sql(SCHOOL_COMBINED_TABLES):
        op.execute(stmt)
    op.drop_index(op.f("ix_timetable_slots_combined_id"), table_name="timetable_slots")
    op.drop_constraint(op.f("fk_timetable_slots_combined_id_combined_periods"),
                       "timetable_slots", type_="foreignkey")
    op.drop_column("timetable_slots", "combined_id")
    op.drop_index(op.f("ix_combined_periods_org_id"), table_name="combined_periods")
    op.drop_table("combined_periods")
