"""My Class endpoints — the class teacher's area (V1-3 `D-03`, expanded 2026-08-05).

`require_academic` throughout: the SERVICE narrows to the caller's own homeroom
(admin: any class) and raises `not_your_class`. Guarding at the router with
`require_admin` would lock out the one person the area exists for; guarding it
per-endpoint would be six copies of one rule.

Route order matters here: `/students/{student_id}/notes` is declared BEFORE any
`/{class_id}/…` route would shadow it — it does not today, because every class
route carries a second segment, but adding `/{class_id}` later would swallow it.

Thin as law 6 requires — every line here is plumbing.
"""

import uuid
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.database import get_db
from app.core.dependencies import require_academic
from app.schemas.my_class import (
    MyClassBands,
    MyClassHomework,
    MyClassHomeworkDay,
    MyClassHomeworkDays,
    MyClassOut,
    MyClassOverview,
    MyClassStudentsOut,
    RegisterOut,
    StudentNoteIn,
    StudentNotesOut,
)
from app.schemas.syllabus_board import SyllabusBoardOut
from app.services.my_class import MyClassService

router = APIRouter()


@router.get("", response_model=MyClassOut)
def my_classes(m: CurrentMember = Depends(require_academic),
               db: Session = Depends(get_db)):
    return MyClassService(db).my_classes(m)


# ── the class teacher's own log about a child ────────────────────────────────
@router.get("/students/{student_id}/notes", response_model=StudentNotesOut)
def student_notes(student_id: uuid.UUID, m: CurrentMember = Depends(require_academic),
                  db: Session = Depends(get_db)):
    """Staff-only, and never reachable from the parent portal — that projection
    is an allowlist built field by field, so this stays out by construction."""
    return MyClassService(db).notes(m, student_id)


@router.post("/students/{student_id}/notes", response_model=StudentNotesOut)
def add_student_note(student_id: uuid.UUID, body: StudentNoteIn,
                     m: CurrentMember = Depends(require_academic),
                     db: Session = Depends(get_db)):
    """Append-only (law 3): no edit, no delete. A correction is a new row."""
    return MyClassService(db).add_note(m, student_id, body)


# ── one class ────────────────────────────────────────────────────────────────
@router.get("/{class_id}/overview", response_model=MyClassOverview)
def overview(class_id: uuid.UUID, m: CurrentMember = Depends(require_academic),
             db: Session = Depends(get_db)):
    """Her six morning questions in one payload: is everyone here, did the work
    come back, how are the subjects moving, how did they do, who needs support."""
    return MyClassService(db).overview(m, class_id)


@router.get("/{class_id}/register", response_model=RegisterOut)
def register(class_id: uuid.UUID, month: str | None = None,
             m: CurrentMember = Depends(require_academic),
             db: Session = Depends(get_db)):
    """The month attendance grid — student × school day, one status per cell."""
    return MyClassService(db).register(m, class_id, month)


@router.get("/{class_id}/students", response_model=MyClassStudentsOut)
def students(class_id: uuid.UUID, days: int = 30,
             m: CurrentMember = Depends(require_academic),
             db: Session = Depends(get_db)):
    """The roster as a table. Each row is a door into that child's file."""
    return MyClassService(db).students(m, class_id, days)


@router.get("/{class_id}/homework", response_model=MyClassHomework)
def homework(class_id: uuid.UUID, days: int = 14,
             m: CurrentMember = Depends(require_academic),
             db: Session = Depends(get_db)):
    """`given ⊇ checked ⊇ graded`, in student-homeworks (V1-17's unit)."""
    return MyClassService(db).homework_board(m, class_id, days)


@router.get("/{class_id}/syllabus", response_model=SyllabusBoardOut)
def syllabus(class_id: uuid.UUID, term_id: uuid.UUID | None = None,
             m: CurrentMember = Depends(require_academic),
             db: Session = Depends(get_db)):
    """The SY-1 chapter table for EVERY subject this class takes.

    The same board Plan → Syllabus renders, at the one scope Plan deliberately
    no longer offers: Plan is her own teaching, this is her homeroom. The
    service establishes the homeroom before widening, so there is no
    `whole_class` flag on the wire for anyone to pass.
    """
    return MyClassService(db).syllabus_board(m, class_id, term_id)


@router.get("/{class_id}/homework/days", response_model=MyClassHomeworkDays)
def homework_days(class_id: uuid.UUID, page: int = 1, size: int = 20,
                  m: CurrentMember = Depends(require_academic),
                  db: Session = Depends(get_db)):
    """What actually went home: today in full, earlier days as openable rows."""
    return MyClassService(db).homework_days(m, class_id, page, size)


@router.get("/{class_id}/homework/day", response_model=MyClassHomeworkDay)
def homework_day(class_id: uuid.UUID, on: date,
                 m: CurrentMember = Depends(require_academic),
                 db: Session = Depends(get_db)):
    """One day opened — every homework in full, and who did not do it."""
    return MyClassService(db).homework_day(m, class_id, on)


@router.get("/{class_id}/bands", response_model=MyClassBands)
def bands(class_id: uuid.UUID, m: CurrentMember = Depends(require_academic),
          db: Session = Depends(get_db)):
    """A/B/C per monitored subject. The unit is the placement, not the child."""
    return MyClassService(db).bands_board(m, class_id)
