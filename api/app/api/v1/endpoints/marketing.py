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
from app.services.marketing import MarketingService

router = APIRouter()


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
