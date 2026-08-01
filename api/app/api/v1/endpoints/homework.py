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
from app.schemas.homework import (
    HomeworkLoad,
    HomeworkOverview,
    HomeworkQueue,
    StudentHomeworkHistory,
)
from app.services.homework import WINDOW_DAYS, HomeworkService

router = APIRouter()


@router.get("/overview", response_model=HomeworkOverview)
def overview(window_days: int = Query(default=WINDOW_DAYS, ge=1, le=120),
             m: CurrentMember = Depends(require_admin), db: Session = Depends(get_db)):
    """School → class → subject completion, plus who is and isn't checking."""
    return HomeworkService(db).overview(m, window_days)


@router.get("/queue", response_model=HomeworkQueue)
def queue(window_days: int = Query(default=30, ge=1, le=120),
          class_subject_id: uuid.UUID | None = None,
          m: CurrentMember = Depends(require_academic),
          db: Session = Depends(get_db)):
    """The teacher's Homework screen (D-36): what she has given, unchecked
    first. `to_check` is the number on the button (S-100)."""
    return HomeworkService(db).queue(m, window_days, class_subject_id)


@router.get("/load", response_model=HomeworkLoad)
def daily_load(class_id: uuid.UUID | None = None,
               days: int = Query(default=14, ge=1, le=90),
               m: CurrentMember = Depends(require_academic),
               db: Session = Depends(get_db)):
    """How many subjects set homework for a class, per day (D-37/S-87).

    `require_academic`, but the service scopes it: an admin sees every class, a
    class teacher sees her own, and a subject teacher sees nothing. That is
    deliberate — the number exists for the staff room, not to make one teacher
    feel they should have set less.
    """
    return HomeworkService(db).daily_load(m, class_id, days)


@router.get("/student/{student_id}", response_model=StudentHomeworkHistory)
def student_history(student_id: uuid.UUID,
                    window_days: int = Query(default=WINDOW_DAYS, ge=1, le=365),
                    m: CurrentMember = Depends(require_academic),
                    db: Session = Depends(get_db)):
    """One student's homework record. Teachers may only read their own students."""
    return HomeworkService(db).student_history(m, student_id, window_days)
