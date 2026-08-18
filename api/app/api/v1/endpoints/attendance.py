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
    AbsenceNoteIn,
    AbsenceNoteOut,
    AbsenceReasonIn,
    AbsenceReasonOut,
    AssemblyMarkIn,
    AssemblyMarkOut,
    AssemblyRosterOut,
    AttendanceMarkIn,
    AttendanceMarkOut,
    AttendanceRosterOut,
    MyAttendanceOut,
)
from app.schemas.my_class import RegisterOut
from app.services.attendance import AttendanceService

router = APIRouter()


@router.get("/roster", response_model=AttendanceRosterOut)
def roster(class_id: uuid.UUID, period_no: int, on_date: date | None = None,
           m: CurrentMember = Depends(require_academic), db: Session = Depends(get_db)):
    return AttendanceService(db).roster(m, class_id, period_no, on_date)


@router.get("/my-classes", response_model=MyAttendanceOut)
def my_classes(on_date: date | None = None,
               m: CurrentMember = Depends(require_academic),
               db: Session = Depends(get_db)):
    """Every class this teacher may take the register for, on any date.

    Founder, 2026-08-05. The school's rule is that the class teacher takes it at
    period one and **any teacher of the class can if she is away** — but until
    now attendance was reachable only from a My Day period card, so the person
    covering had no door into it. This widens no permission (the service uses
    the same `assert_can_take_class` set); it adds the screen that rule needs.
    """
    return AttendanceService(db).my_board(m, on_date)


@router.get("/register", response_model=RegisterOut)
def class_register(class_id: uuid.UUID, month: str | None = None,
                   m: CurrentMember = Depends(require_academic),
                   db: Session = Depends(get_db)):
    """The month register book for a class this teacher takes — student × day.

    The same drawing My Class shows its class teacher (`build_register`), behind
    a wider door: a teacher who may be asked to take the roll must be able to
    read it. View only; writing goes through `/attendance/mark`.
    """
    return AttendanceService(db).class_register(m, class_id, month)


@router.post("/mark", response_model=AttendanceMarkOut)
def mark(body: AttendanceMarkIn, m: CurrentMember = Depends(require_academic),
         db: Session = Depends(get_db)):
    return AttendanceService(db).mark(m, body)


# ── the whole-school register, taken at assembly (TT-6) ──────────────────────
@router.get("/assembly", response_model=AssemblyRosterOut)
def assembly_sheet(session_id: uuid.UUID, on_date: date | None = None,
                   period_no: int | None = None,
                   m: CurrentMember = Depends(require_academic),
                   db: Session = Depends(get_db)):
    """Every child in the hall, grouped by class (founder, 2026-08-18).

    The door is the BLOCK, not the classes: the person who takes assembly teaches
    almost none of the school. `assert_may_take_block` is what admits her, and
    the classes she can reach are only the ones that block holds on the grid at
    that period — never a class list she gets to name.
    """
    return AttendanceService(db).assembly_sheet(m, session_id, on_date, period_no)


@router.post("/assembly", response_model=AssemblyMarkOut)
def mark_assembly(body: AssemblyMarkIn, m: CurrentMember = Depends(require_academic),
                  db: Session = Depends(get_db)):
    """One roll call in the hall → one register per class, filed on the block's
    period. Capture-by-exception: "everyone is here" posts an empty list."""
    return AttendanceService(db).mark_assembly(m, body)


# ── V1-3: reasons + informed absence (D-02 / S-24) ───────────────────────────
@router.put("/absences/reason", response_model=AbsenceReasonOut)
def set_absence_reason(body: AbsenceReasonIn,
                       m: CurrentMember = Depends(require_academic),
                       db: Session = Depends(get_db)):
    """Admin OR teacher, always AFTER capture (D-02 step 3). The reason is what
    turns a red row amber (D-86)."""
    return AttendanceService(db).set_absence_reason(m, body)


@router.post("/absences/notes", response_model=AbsenceNoteOut)
def add_absence_note(body: AbsenceNoteIn,
                     m: CurrentMember = Depends(require_academic),
                     db: Session = Depends(get_db)):
    """Informed/planned absence — append-only; suppresses the guardian alert
    for the covered days and pre-explains them on every board."""
    return AttendanceService(db).add_absence_note(m, body)


@router.get("/absences/{student_id}/notes", response_model=list[AbsenceNoteOut])
def list_absence_notes(student_id: uuid.UUID,
                       m: CurrentMember = Depends(require_academic),
                       db: Session = Depends(get_db)):
    return AttendanceService(db).list_absence_notes(m, student_id)
