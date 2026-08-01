"""Homework analytics endpoints (HW-1).

Capture lives on `/classroom/homework/*` (the teacher's surface). This router is
the read side: the admin's report, and one student's history.
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.database import get_db
from app.core.dependencies import require_academic, require_admin
from app.schemas.homework import HomeworkOverview, StudentHomeworkHistory
from app.services.homework import WINDOW_DAYS, HomeworkService

router = APIRouter()


@router.get("/overview", response_model=HomeworkOverview)
def overview(window_days: int = Query(default=WINDOW_DAYS, ge=1, le=120),
             m: CurrentMember = Depends(require_admin), db: Session = Depends(get_db)):
    """School → class → subject completion, plus who is and isn't checking."""
    return HomeworkService(db).overview(m, window_days)


@router.get("/student/{student_id}", response_model=StudentHomeworkHistory)
def student_history(student_id: uuid.UUID,
                    window_days: int = Query(default=WINDOW_DAYS, ge=1, le=365),
                    m: CurrentMember = Depends(require_academic),
                    db: Session = Depends(get_db)):
    """One student's homework record. Teachers may only read their own students."""
    return HomeworkService(db).student_history(m, student_id, window_days)
