"""Marketing endpoints — the public "book a demo" capture.

POST is the ONLY unauthenticated write in the school modules. It is rate-limited
by IP and returns an acknowledgement, never data. Reading the leads back is
super-admin only.
"""

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_super_admin
from app.core.rate_limit import limiter
from app.schemas.marketing import (
    DemoRequestAck,
    DemoRequestCreate,
    DemoRequestDetail,
    DemoRequestOut,
    DemoRequestUpdate,
)
from app.schemas.tiers import PlanPriceOut
from app.services.marketing import MarketingService
from app.services.tiers import TierService

router = APIRouter()


@router.get("/plans", response_model=list[PlanPriceOut])
def public_plan_prices(db: Session = Depends(get_db)) -> list[PlanPriceOut]:
    """The public price list — what the marketing site quotes.

    Public on purpose, and **fetched rather than typed** (`D-106`): the founder's
    "the plan number and costing might change regularly because we are just
    launching" is only true if changing a price needs no deploy. The site reads
    this; the operator edits it from `/platform`.

    Carries no school context — just the list price per tier, in paise per
    student per month. What an existing school actually pays is frozen in its
    own `plan_changes` row and never moves when this does.
    """
    return TierService(db).list_prices()


@router.post("/demo-requests", response_model=DemoRequestAck)
@limiter.limit("5/minute")
def create_demo_request(
    request: Request, body: DemoRequestCreate, db: Session = Depends(get_db)
) -> DemoRequestAck:
    row = MarketingService(db).create_demo_request(body)
    return DemoRequestAck(id=row.id)


@router.get("/demo-requests", response_model=list[DemoRequestOut])
def list_demo_requests(
    member=Depends(require_super_admin), db: Session = Depends(get_db)
) -> list[DemoRequestOut]:
    return MarketingService(db).list_demo_requests()


@router.get("/demo-requests/{request_id}", response_model=DemoRequestDetail)
def get_demo_request(
    request_id: uuid.UUID,
    member=Depends(require_super_admin),
    db: Session = Depends(get_db),
) -> DemoRequestDetail:
    return MarketingService(db).demo_request_detail(request_id)


@router.post("/demo-requests/{request_id}/notes", response_model=DemoRequestDetail)
def add_demo_request_note(
    request_id: uuid.UUID,
    body: DemoRequestUpdate,
    member=Depends(require_super_admin),
    db: Session = Depends(get_db),
) -> DemoRequestDetail:
    """Append one history row: a remark, a status move, or both."""
    return MarketingService(db).add_note(member, request_id, body)
