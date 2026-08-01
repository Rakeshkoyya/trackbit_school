"""V1-5: the homework verdict vocabulary (D-85, D-34, S-98).

`homework_results.status` was `not_done | partial` — enough to say a child did
not do the work, and unable to say anything else. Three verdicts join it, and
each one exists because the two-value version was writing something untrue into
a child's record:

  * **late** (`D-85`) — did it, after the deadline. A status the teacher sets at
    any time, with no threshold and no expiry; it counts as done and is reported
    separately. `D-85` deliberately removed the working-day gap arithmetic the
    first design had: teacher-delay is *derived* from "nothing checked for N
    days" and never written against a student.
  * **carried** (`D-34`) — was absent when it was set. Pending, not a miss. It
    leaves every completion denominator, the streak and the red list.
  * **waived** (`S-98`) — the teacher decided the backlog is not required.
    Without it, carried items accumulate for every absence in the year and the
    parent's pending list never clears.

"Done on time" remains the **absence of a row**, which is what keeps the capture
one tap for the norm (P1v2). Nothing is dropped or rewritten: the widening is
additive and every existing row keeps its meaning.

Revision ID: c5d6e7f8a9b0
Revises: b4c5d6e7f8a9
"""

from alembic import op

revision = "c5d6e7f8a9b0"
down_revision = "b4c5d6e7f8a9"
branch_labels = None
depends_on = None

_OLD = "status IN ('not_done', 'partial')"
_NEW = "status IN ('not_done', 'partial', 'late', 'carried', 'waived')"


def upgrade() -> None:
    op.drop_constraint("homework_result_status_valid", "homework_results", type_="check")
    op.create_check_constraint("homework_result_status_valid", "homework_results", _NEW)


def downgrade() -> None:
    # The new verdicts have no two-value equivalent, and guessing one would put
    # a false fact in a child's record — late/carried/waived are dropped rather
    # than collapsed into not_done.
    op.execute("DELETE FROM homework_results "
               "WHERE status IN ('late', 'carried', 'waived')")
    op.drop_constraint("homework_result_status_valid", "homework_results", type_="check")
    op.create_check_constraint("homework_result_status_valid", "homework_results", _OLD)
