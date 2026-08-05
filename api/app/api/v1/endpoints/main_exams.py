"""Main exams — the school's exam calendar and its papers (founder, 2026-08-05).

Reads are `require_academic`: the SERVICE narrows a teacher to her assigned
classes and marks each row `can_edit`. Writes to the exam LIST are
`require_admin` — the exams a school holds are the admin's declaration, and a
teacher reads that list locked (founder).

Writing a paper's MARKS is not here at all. It is `POST /assessments/exams`,
unchanged, with `exam_event_id` set — one write path for every mark in the
product, so the Plan → Exams grid and the scores capture page cannot diverge.
That path now also asks `MainExamService.assert_can_record_subject`, which is
the narrower "is this subject yours" rule.

Route order: `/board` is declared before `/{event_id}` — a literal segment after
a path parameter is shadowed by it, and `board` would be parsed as a UUID.
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.database import get_db
from app.core.dependencies import require_academic, require_admin
from app.schemas.common import MessageResponse
from app.schemas.main_exams import (
    MainExamBoard,
    MainExamDetail,
    MainExamIn,
    MainExamRow,
)
from app.services.main_exams import MainExamService

router = APIRouter()


@router.get("", response_model=MainExamBoard)
def board(year_id: uuid.UUID | None = None,
          m: CurrentMember = Depends(require_academic),
          db: Session = Depends(get_db)):
    """Every exam the school has declared this year, with its progress."""
    return MainExamService(db).board(m, year_id)


@router.post("", response_model=MainExamRow)
def create(body: MainExamIn, m: CurrentMember = Depends(require_admin),
           db: Session = Depends(get_db)):
    return MainExamService(db).create(m, body)


@router.get("/{event_id}", response_model=MainExamDetail)
def detail(event_id: uuid.UUID, m: CurrentMember = Depends(require_academic),
           db: Session = Depends(get_db)):
    """Class × subject. Every row a teacher may SEE, `can_edit` on the ones that
    are hers — reading a colleague's card is wider than writing her marks, and
    that asymmetry is the point."""
    return MainExamService(db).detail(m, event_id)


@router.patch("/{event_id}", response_model=MainExamRow)
def update(event_id: uuid.UUID, body: MainExamIn,
           m: CurrentMember = Depends(require_admin),
           db: Session = Depends(get_db)):
    return MainExamService(db).update(m, event_id, body)


@router.delete("/{event_id}", response_model=MessageResponse)
def remove(event_id: uuid.UUID, m: CurrentMember = Depends(require_admin),
           db: Session = Depends(get_db)):
    """Refused once any paper has been recorded under it — deleting the block
    that owns a term's marks would orphan them silently."""
    MainExamService(db).delete(m, event_id)
    return MessageResponse(message="Exam removed.")
