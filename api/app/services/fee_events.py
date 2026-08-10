"""The fee desk's actor log (`D-124`, FE-1).

The founder's requirement, in his own words:

    *"in case there are 3 admins looking into fee collections, then if admin1
    changes something and admin2 feel something is changed and check the action
    logs and understand and maybe asks in person to get clarity"*

That last clause is the design brief, and it is why this module exists at all.
The log is not for auditors — it is so **one colleague can find the other and
ask**. Two consequences follow directly:

* **`actor_name` is written into the row**, not resolved by join at read time.
  The person who needs to be asked must still be nameable after the account is
  deactivated, and a log that reads "—" is a log nobody can act on.
* **`summary` is a finished English sentence**, composed here at write time.
  Every screen shows the same words. This codebase's most-repeated defect is the
  same fact rendered two ways in two places; a log is the last place that should
  happen, because its whole job is to settle an argument about what happened.

**Money still lives in `fee_transactions`.** That table is summable and must stay
that way. This one is the narrative — including every action that has no money
and no student at all, like pricing a class, which `fee_transactions` physically
cannot hold (`student_fee_id` is NOT NULL there).

Append-only, law 3: nothing in this module updates or deletes a row. A correction
is another event.
"""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.models import FEE_EVENT_KINDS, FeeEvent


def record(
    db: Session,
    m: CurrentMember,
    kind: str,
    summary: str,
    *,
    student_fee_id: uuid.UUID | None = None,
    fee_structure_id: uuid.UUID | None = None,
    academic_year_id: uuid.UUID | None = None,
    meta: dict[str, Any] | None = None,
) -> FeeEvent:
    """Append one event. Call it from the service that made the change, in the
    same transaction, so an action and its log commit or roll back together.

    `kind` is checked against the vocabulary rather than accepted freely: a typo
    would create a kind no reader filters on, and the row would be invisible in
    exactly the situation it was written for. That is a programming error, so it
    raises `ValueError` rather than an `AppError` — no user input reaches it.
    """
    if kind not in FEE_EVENT_KINDS:
        raise ValueError(
            f"Unknown fee event kind {kind!r}. Add it to FEE_EVENT_KINDS first."
        )
    event = FeeEvent(
        org_id=m.org_id,
        student_fee_id=student_fee_id,
        fee_structure_id=fee_structure_id,
        academic_year_id=academic_year_id,
        kind=kind,
        summary=summary,
        meta=meta or {},
        actor_member_id=m.membership.id,
        actor_name=m.user.name,
    )
    db.add(event)
    return event


def for_student_fee(
    db: Session, org_id: uuid.UUID, student_fee_id: uuid.UUID, limit: int = 200
) -> list[FeeEvent]:
    """This child's history, newest first. Org-scoped explicitly — law 2 is
    defence in depth, not the guard."""
    return list(
        db.scalars(
            select(FeeEvent)
            .where(FeeEvent.org_id == org_id, FeeEvent.student_fee_id == student_fee_id)
            .order_by(FeeEvent.created_at.desc(), FeeEvent.id.desc())
            .limit(limit)
        )
    )


def for_year(
    db: Session, org_id: uuid.UUID, academic_year_id: uuid.UUID, limit: int = 200
) -> list[FeeEvent]:
    """Everything that happened at the desk this year — the read admin2 opens
    when something changed and she does not yet know which child it was."""
    return list(
        db.scalars(
            select(FeeEvent)
            .where(
                FeeEvent.org_id == org_id,
                FeeEvent.academic_year_id == academic_year_id,
            )
            .order_by(FeeEvent.created_at.desc(), FeeEvent.id.desc())
            .limit(limit)
        )
    )
