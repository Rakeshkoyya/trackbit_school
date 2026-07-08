"""Daily checks / recommendations endpoints (V2-M5, SPRD2 §5.5).

GET generates-if-absent (zero teacher setup) and returns the period's checks; the
service checks the teacher owns the class-subject. Confirm marks "class did it ✓"
and records only the tapped deviations."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.database import get_db
from app.core.dependencies import require_academic
from app.schemas.checks import CheckConfirmIn, ChecksOut, DailyCheckOut
from app.services.recommendations import RecommendationsService

router = APIRouter()


@router.get("", response_model=ChecksOut)
def get_checks(class_subject_id: uuid.UUID, on_date: date | None = None,
               m: CurrentMember = Depends(require_academic), db: Session = Depends(get_db)):
    return RecommendationsService(db).ensure(m, class_subject_id, on_date)


@router.post("/{check_id}/confirm", response_model=DailyCheckOut)
def confirm_check(check_id: uuid.UUID, body: CheckConfirmIn,
                  m: CurrentMember = Depends(require_academic), db: Session = Depends(get_db)):
    return RecommendationsService(db).confirm(m, check_id, body)
