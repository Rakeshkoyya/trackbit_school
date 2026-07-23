"""Marketing endpoints — the public "book a demo" capture.

POST is the ONLY unauthenticated write in the school modules. It is rate-limited
by IP and returns an acknowledgement, never data. Reading the leads back is
super-admin only.
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_super_admin
from app.core.rate_limit import limiter
from app.schemas.marketing import DemoRequestAck, DemoRequestCreate, DemoRequestOut
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
