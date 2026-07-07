"""Classroom capture endpoints (M2, SPRD §5.2).

My Day / log / homework are the teacher's daily surface (require_academic — the
service further checks the class is theirs). Compliance is coordinator/director.
"""

import uuid
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.database import get_db
from app.core.dependencies import require_academic, require_coordinator_up
from app.schemas.classroom import (
    ComplianceOut,
    HomeworkCheckIn,
    HomeworkIn,
    HomeworkOut,
    LessonLogIn,
    LessonLogOut,
    MyDayOut,
)
from app.services.classroom import ClassroomService

router = APIRouter()


@router.get("/my-day", response_model=MyDayOut)
def my_day(on_date: date | None = None, m: CurrentMember = Depends(require_academic),
           db: Session = Depends(get_db)):
    return ClassroomService(db).my_day(m, on_date)


@router.post("/lesson-logs", response_model=LessonLogOut)
def create_log(body: LessonLogIn, m: CurrentMember = Depends(require_academic),
               db: Session = Depends(get_db)):
    return ClassroomService(db).log(m, body)


@router.post("/homework", response_model=HomeworkOut)
def add_homework(body: HomeworkIn, m: CurrentMember = Depends(require_academic),
                 db: Session = Depends(get_db)):
    return ClassroomService(db).add_homework(m, body)


@router.post("/homework/{assignment_id}/check", response_model=HomeworkOut)
def check_homework(assignment_id: uuid.UUID, body: HomeworkCheckIn,
                   m: CurrentMember = Depends(require_academic), db: Session = Depends(get_db)):
    return ClassroomService(db).check_homework(m, assignment_id, body)


@router.get("/compliance", response_model=ComplianceOut)
def compliance(on_date: date | None = None, m: CurrentMember = Depends(require_coordinator_up),
               db: Session = Depends(get_db)):
    return ClassroomService(db).compliance(m, on_date)
