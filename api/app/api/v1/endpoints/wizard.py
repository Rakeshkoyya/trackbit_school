"""Setup wizard endpoints (V2-M1, SPRD2 §5.1) — admin-only, resumable.

State is orchestration only; each step's data is written through the existing
module endpoints. Progress is derived from the real tables."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.database import get_db
from app.core.dependencies import require_admin
from app.schemas.wizard import WizardAdvanceIn, WizardStateOut
from app.services.wizard import WizardService

router = APIRouter()


@router.get("/state", response_model=WizardStateOut)
def state(m: CurrentMember = Depends(require_admin), db: Session = Depends(get_db)):
    return WizardService(db).state(m)


@router.post("/advance", response_model=WizardStateOut)
def advance(body: WizardAdvanceIn, m: CurrentMember = Depends(require_admin),
            db: Session = Depends(get_db)):
    return WizardService(db).advance(m, body)


@router.post("/complete", response_model=WizardStateOut)
def complete(m: CurrentMember = Depends(require_admin), db: Session = Depends(get_db)):
    return WizardService(db).complete(m)


@router.post("/reset", response_model=WizardStateOut)
def reset(m: CurrentMember = Depends(require_admin), db: Session = Depends(get_db)):
    return WizardService(db).reset(m)
