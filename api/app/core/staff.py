"""Who counts as a member of the school's staff.

`memberships` answers *"who may sign in to this org"*, which is not the same
question as *"who works here"* — and every staff roster in the product had been
reading the first as though it were the second.

The gap is the **platform operator**. V3-P0 made school creation the dev's job,
and `PlatformService.create_org` joins the operator into each new school as an
admin so they can run setup and hand over credentials. That membership is real
and has to keep working — the operator must be able to enter the org — but the
account is the vendor's, not an employee of the school. Counted as staff it
became: a person the school is asked to mark present every morning, a name in the
staff directory, a birthday in the day's notice, a candidate to cover period 4,
a row in the leave queue, and eight unaccounted-for periods a day in the
day-book's capacity.

So `not_operator()` is the filter every **roster** read applies, and no
**permission** read applies. Guards resolve the operator's membership exactly as
before (`core/dependencies.py`, `core/visibility.py`, `services/auth.py`,
`services/tokens.py`, `core/plans.py`) — hiding somebody from a staff list must
never lock them out of the org they were deliberately let into. Keep that split:
a roster read that grows a permission responsibility, or vice versa, is how this
bug gets reintroduced from the other side.
"""

from sqlalchemy import select
from sqlalchemy.sql.elements import ColumnElement

from app.models import Membership, User


def not_operator() -> ColumnElement[bool]:
    """Predicate for `Membership` queries: everyone except platform operators.

    Deliberately an **uncorrelated** `NOT IN` over the operator user-ids, not a
    join and not a correlated EXISTS. Most callers already
    `.join(User, User.id == Membership.user_id)` for the name, so an EXISTS
    naming `User` would bind to the outer join rather than to a subquery of its
    own — right by accident here, wrong the first time somebody reuses it in a
    query shaped differently. This form drops into any `.where(...)` without
    touching the query's FROM, its selected columns or its cardinality.

    `users.is_super_admin` and `memberships.user_id` are both NOT NULL, so the
    `NOT IN` carries none of the three-valued-logic trap.
    """
    return Membership.user_id.not_in(
        select(User.id).where(User.is_super_admin.is_(True))
    )
