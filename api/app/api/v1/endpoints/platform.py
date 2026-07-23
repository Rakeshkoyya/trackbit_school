"""Platform endpoints (super-admin only): the layer above orgs.

The operator creates each school, enters it to run setup from the data the
school handed over, and only then gives the school admin their credentials.
"""

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_super_admin
from app.core.rate_limit import limiter
from app.schemas.auth import SessionResponse
from app.schemas.platform import CreateSchoolRequest, CreateSchoolResult, PlatformOrgOut
from app.services.platform import PlatformService

router = APIRouter()


@router.get("/orgs", response_model=list[PlatformOrgOut])
def list_orgs(
    member=Depends(require_super_admin), db: Session = Depends(get_db)
) -> list[PlatformOrgOut]:
    return PlatformService(db).list_orgs()


@router.post("/orgs", response_model=CreateSchoolResult)
@limiter.limit("10/minute")
def create_school(
    request: Request,
    body: CreateSchoolRequest,
    member=Depends(require_super_admin),
    db: Session = Depends(get_db),
) -> CreateSchoolResult:
    return PlatformService(db).create_school(member, body)


@router.post("/orgs/{org_id}/enter", response_model=SessionResponse)
@limiter.limit("30/minute")
def enter_org(
    request: Request,
    org_id: uuid.UUID,
    member=Depends(require_super_admin),
    db: Session = Depends(get_db),
) -> SessionResponse:
    return SessionResponse(**PlatformService(db).enter_org(member, org_id))
