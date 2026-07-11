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
    ObservationSectionIn,
    ObservationsOut,
)
from app.schemas.common import MessageResponse
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


@router.delete("/lesson-logs/{log_id}", response_model=MessageResponse)
def delete_log(log_id: uuid.UUID, m: CurrentMember = Depends(require_academic),
               db: Session = Depends(get_db)):
    """Undo a mis-tapped topic log from the period page."""
    ClassroomService(db).delete_log(m, log_id)
    return MessageResponse(message="Log removed.")


@router.post("/homework", response_model=HomeworkOut)
def add_homework(body: HomeworkIn, m: CurrentMember = Depends(require_academic),
                 db: Session = Depends(get_db)):
    return ClassroomService(db).add_homework(m, body)


@router.post("/homework/{assignment_id}/check", response_model=HomeworkOut)
def check_homework(assignment_id: uuid.UUID, body: HomeworkCheckIn,
                   m: CurrentMember = Depends(require_academic), db: Session = Depends(get_db)):
    return ClassroomService(db).check_homework(m, assignment_id, body)


# ── deep log — optional lesson observations (teacher-view redesign) ──────────
@router.get("/observations", response_model=ObservationsOut)
def observations(class_subject_id: uuid.UUID, on_date: date | None = None,
                 period_id: uuid.UUID | None = None,
                 m: CurrentMember = Depends(require_academic), db: Session = Depends(get_db)):
    return ClassroomService(db).observations(m, class_subject_id, on_date, period_id)


@router.put("/observations", response_model=ObservationsOut)
def save_observation_section(body: ObservationSectionIn,
                             m: CurrentMember = Depends(require_academic),
                             db: Session = Depends(get_db)):
    """Full-replace ONE section (e.g. "Vocabulary") — concepts + only the tapped
    per-student deviations (P1v2)."""
    return ClassroomService(db).save_observation_section(m, body)


@router.delete("/observations", response_model=MessageResponse)
def delete_observation_section(class_subject_id: uuid.UUID, section: str,
                               on_date: date | None = None,
                               period_id: uuid.UUID | None = None,
                               m: CurrentMember = Depends(require_academic),
                               db: Session = Depends(get_db)):
    ClassroomService(db).delete_observation_section(m, class_subject_id, section,
                                                    on_date, period_id)
    return MessageResponse(message="Section removed.")


@router.get("/compliance", response_model=ComplianceOut)
def compliance(on_date: date | None = None, m: CurrentMember = Depends(require_coordinator_up),
               db: Session = Depends(get_db)):
    return ClassroomService(db).compliance(m, on_date)
