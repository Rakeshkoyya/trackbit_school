"""Per-period attendance endpoints (V2-M4, SPRD2 §5.4).

Marking is a teacher surface (require_academic — the service further checks the
teacher owns a subject in the class). Capture-by-exception only: "all present"
posts with an empty exceptions list."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.database import get_db
from app.core.dependencies import require_academic
from app.schemas.attendance import (
    AttendanceMarkIn,
    AttendanceMarkOut,
    AttendanceRosterOut,
)
from app.services.attendance import AttendanceService

router = APIRouter()


@router.get("/roster", response_model=AttendanceRosterOut)
def roster(class_id: uuid.UUID, period_no: int, on_date: date | None = None,
           m: CurrentMember = Depends(require_academic), db: Session = Depends(get_db)):
    return AttendanceService(db).roster(m, class_id, period_no, on_date)


@router.post("/mark", response_model=AttendanceMarkOut)
def mark(body: AttendanceMarkIn, m: CurrentMember = Depends(require_academic),
         db: Session = Depends(get_db)):
    return AttendanceService(db).mark(m, body)
