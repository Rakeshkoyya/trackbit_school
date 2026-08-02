"""Events & dates — the what's-on feed and the approval sheet (V1-7).

The feed is `require_academic`: a teacher's My Day strip and the admin's card
are the same computation at two depths (module §1), so they are one endpoint.

Everything that *decides* is admin-only, because approval is the commit
(`D-57`) — and `/events/suggestions` is admin-only for `Q-64` (a): the teacher's
strip never shows anything provisional. Its whole value is that it costs zero
attention and is never wrong.
"""

import uuid
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.database import get_db
from app.core.dependencies import require_academic, require_admin
from app.schemas.events import (
    ApproveIn,
    CostIn,
    DecisionOut,
    DismissIn,
    LockCost,
    SuggestionOut,
    WhatsOn,
)
from app.services.whats_on import DEFAULT_HORIZON, WhatsOnService

router = APIRouter()


@router.get("/whats-on", response_model=WhatsOn)
def whats_on(on_date: date | None = None, horizon: int = DEFAULT_HORIZON,
             m: CurrentMember = Depends(require_academic),
             db: Session = Depends(get_db)):
    """Today's specials and what is coming — birthdays, the school's own
    calendar, and nothing provisional."""
    return WhatsOnService(db).feed(m, on_date, min(max(horizon, 1), 120),
                                   for_admin=m.membership.org_role == "admin")


@router.get("/suggestions", response_model=list[SuggestionOut])
def suggestions(horizon: int = 90, m: CurrentMember = Depends(require_admin),
                db: Session = Depends(get_db)):
    return WhatsOnService(db).suggestions(m, min(max(horizon, 1), 365))


@router.post("/suggestions/{observance_id}/approve", response_model=DecisionOut)
def approve(observance_id: uuid.UUID, body: ApproveIn,
            m: CurrentMember = Depends(require_admin), db: Session = Depends(get_db)):
    """The one route from a suggestion to the school's calendar, and it needs a
    human press. The date is the admin's, not the catalogue's (`D-79`)."""
    return WhatsOnService(db).approve(m, observance_id, body)


@router.post("/suggestions/{observance_id}/dismiss", response_model=DecisionOut)
def dismiss(observance_id: uuid.UUID, body: DismissIn,
            m: CurrentMember = Depends(require_admin), db: Session = Depends(get_db)):
    return WhatsOnService(db).dismiss(m, observance_id, body)


@router.post("/cost", response_model=LockCost)
def cost(body: CostIn, m: CurrentMember = Depends(require_admin),
         db: Session = Depends(get_db)):
    """`S-143` — what this lock removes, said before it is committed."""
    return WhatsOnService(db).lock_cost(m, body)
