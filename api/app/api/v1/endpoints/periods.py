"""Class-period endpoints (V2-P6).

The period card is a teacher surface (require_academic — the service further checks
the teacher owns a subject in the class). `POST /periods/open` is what sits behind
the card's "Start attendance" button: it is the first write of the period, and it
is idempotent, so a double-tap is harmless.
"""

import uuid
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.database import get_db
from app.core.dependencies import require_academic
from app.schemas.periods import (
    PeriodCardOut,
    PeriodNotHeldIn,
    PeriodOpenIn,
    PeriodOut,
    RecordableOut,
)
from app.services.classroom import ClassroomService
from app.services.periods import PeriodService

router = APIRouter()


@router.get("/recordable", response_model=RecordableOut)
def recordable(on_date: date | None = None,
               m: CurrentMember = Depends(require_academic),
               db: Session = Depends(get_db)):
    """`FB-1a` — the classes, subjects and periods this member could record
    off the timetable. Read-only; it opens no period and writes nothing."""
    return ClassroomService(db).recordable(m, on_date)


@router.get("/card", response_model=PeriodCardOut)
def card(class_id: uuid.UUID, period_no: int, on_date: date | None = None,
         class_subject_id: uuid.UUID | None = None,
         m: CurrentMember = Depends(require_academic), db: Session = Depends(get_db)):
    """Read-only. `period_id` is null until the period is opened.

    `class_subject_id` names the subject when the timetable has nothing here
    (`FB-1a`); it is a fallback, never an override.
    """
    return ClassroomService(db).period_card(
        m, class_id, period_no, on_date, class_subject_id)


@router.post("/open", response_model=PeriodOut)
def open_period(body: PeriodOpenIn, m: CurrentMember = Depends(require_academic),
                db: Session = Depends(get_db)):
    return PeriodService(db).open(
        m, body.class_id, body.period_no, body.class_subject_id, body.date)


@router.post("/{period_id}/close", response_model=PeriodOut)
def close_period(period_id: uuid.UUID, m: CurrentMember = Depends(require_academic),
                 db: Session = Depends(get_db)):
    return PeriodService(db).close(m, period_id)


@router.post("/{period_id}/reopen", response_model=PeriodOut)
def reopen_period(period_id: uuid.UUID, m: CurrentMember = Depends(require_academic),
                  db: Session = Depends(get_db)):
    return PeriodService(db).reopen(m, period_id)


@router.post("/{period_id}/not-held", response_model=PeriodOut)
def not_held(period_id: uuid.UUID, body: PeriodNotHeldIn,
             m: CurrentMember = Depends(require_academic), db: Session = Depends(get_db)):
    return PeriodService(db).not_held(m, period_id, body.reason, body.event_id)
