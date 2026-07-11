"""Academic master-data endpoints (SPRD §5.1).

Reads are open to any academic role; structural writes are coordinator/director
(SPRD §3.3). Thin plumbing only — logic lives in AcademicService.
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.database import get_db
from app.core.dependencies import get_current_member, require_academic, require_admin
from app.schemas.academics import (
    AllocationSetIn,
    ClassAllocationOut,
    ClassCreate,
    ClassOut,
    ClassSubjectCreate,
    ClassSubjectOut,
    ClassSubjectUpdate,
    ClassUpdate,
    SubjectCreate,
    SubjectOut,
    TermCreate,
    TermOut,
    TermUpdate,
    YearCreate,
    YearOut,
    YearUpdate,
)
from app.schemas.calendar import (
    CalendarBulkIn,
    CalendarEventCreate,
    CalendarEventOut,
    CalendarSummary,
    ExamPortionIn,
    ExamPortionOut,
)
from app.schemas.common import MessageResponse
from app.services.academics import AcademicService
from app.services.calendar import CalendarService, ExamPortionService

router = APIRouter()


# ── years ────────────────────────────────────────────────────────────────────
# Years are org-level master data (the global academic-year switcher, SPRD §6.3
# header). Readable by any member — incl. office, who scopes fees by year — while
# writes stay coordinator/director.
@router.get("/years", response_model=list[YearOut])
def list_years(m: CurrentMember = Depends(get_current_member), db: Session = Depends(get_db)):
    return AcademicService(db).list_years(m)


@router.post("/years", response_model=YearOut)
def create_year(body: YearCreate, m: CurrentMember = Depends(require_admin),
                db: Session = Depends(get_db)):
    return AcademicService(db).create_year(m, body)


@router.patch("/years/{year_id}", response_model=YearOut)
def update_year(year_id: uuid.UUID, body: YearUpdate,
                m: CurrentMember = Depends(require_admin), db: Session = Depends(get_db)):
    return AcademicService(db).update_year(m, year_id, body)


@router.post("/years/{year_id}/activate", response_model=YearOut)
def activate_year(year_id: uuid.UUID, m: CurrentMember = Depends(require_admin),
                  db: Session = Depends(get_db)):
    return AcademicService(db).activate_year(m, year_id)


@router.delete("/years/{year_id}", response_model=MessageResponse)
def delete_year(year_id: uuid.UUID, m: CurrentMember = Depends(require_admin),
                db: Session = Depends(get_db)):
    AcademicService(db).delete_year(m, year_id)
    return MessageResponse(message="Year deleted.")


# ── terms ────────────────────────────────────────────────────────────────────
@router.get("/terms", response_model=list[TermOut])
def list_terms(year_id: uuid.UUID | None = None,
               m: CurrentMember = Depends(require_academic), db: Session = Depends(get_db)):
    return AcademicService(db).list_terms(m, year_id)


@router.post("/terms", response_model=TermOut)
def create_term(body: TermCreate, m: CurrentMember = Depends(require_admin),
                db: Session = Depends(get_db)):
    return AcademicService(db).create_term(m, body)


@router.patch("/terms/{term_id}", response_model=TermOut)
def update_term(term_id: uuid.UUID, body: TermUpdate,
                m: CurrentMember = Depends(require_admin), db: Session = Depends(get_db)):
    return AcademicService(db).update_term(m, term_id, body)


@router.delete("/terms/{term_id}", response_model=MessageResponse)
def delete_term(term_id: uuid.UUID, m: CurrentMember = Depends(require_admin),
                db: Session = Depends(get_db)):
    AcademicService(db).delete_term(m, term_id)
    return MessageResponse(message="Term deleted.")


# ── subjects ─────────────────────────────────────────────────────────────────
@router.get("/subjects", response_model=list[SubjectOut])
def list_subjects(m: CurrentMember = Depends(require_academic), db: Session = Depends(get_db)):
    return AcademicService(db).list_subjects(m)


@router.post("/subjects", response_model=SubjectOut)
def create_subject(body: SubjectCreate, m: CurrentMember = Depends(require_admin),
                   db: Session = Depends(get_db)):
    return AcademicService(db).create_subject(m, body)


@router.delete("/subjects/{subject_id}", response_model=MessageResponse)
def delete_subject(subject_id: uuid.UUID, m: CurrentMember = Depends(require_admin),
                   db: Session = Depends(get_db)):
    AcademicService(db).delete_subject(m, subject_id)
    return MessageResponse(message="Subject deleted.")


# ── classes ──────────────────────────────────────────────────────────────────
@router.get("/classes", response_model=list[ClassOut])
def list_classes(year_id: uuid.UUID | None = None,
                 m: CurrentMember = Depends(require_academic), db: Session = Depends(get_db)):
    return AcademicService(db).list_classes(m, year_id)


@router.post("/classes", response_model=ClassOut)
def create_class(body: ClassCreate, m: CurrentMember = Depends(require_admin),
                 db: Session = Depends(get_db)):
    return AcademicService(db).create_class(m, body)


@router.patch("/classes/{class_id}", response_model=ClassOut)
def update_class(class_id: uuid.UUID, body: ClassUpdate,
                 m: CurrentMember = Depends(require_admin), db: Session = Depends(get_db)):
    return AcademicService(db).update_class(m, class_id, body)


@router.delete("/classes/{class_id}", response_model=MessageResponse)
def delete_class(class_id: uuid.UUID, m: CurrentMember = Depends(require_admin),
                 db: Session = Depends(get_db)):
    AcademicService(db).delete_class(m, class_id)
    return MessageResponse(message="Class deleted.")


# ── class–subjects ───────────────────────────────────────────────────────────
@router.get("/classes/{class_id}/subjects", response_model=list[ClassSubjectOut])
def list_class_subjects(class_id: uuid.UUID, m: CurrentMember = Depends(require_academic),
                        db: Session = Depends(get_db)):
    return AcademicService(db).list_class_subjects(m, class_id)


@router.post("/class-subjects", response_model=ClassSubjectOut)
def create_class_subject(body: ClassSubjectCreate,
                         m: CurrentMember = Depends(require_admin),
                         db: Session = Depends(get_db)):
    return AcademicService(db).create_class_subject(m, body)


@router.patch("/class-subjects/{cs_id}", response_model=ClassSubjectOut)
def update_class_subject(cs_id: uuid.UUID, body: ClassSubjectUpdate,
                         m: CurrentMember = Depends(require_admin),
                         db: Session = Depends(get_db)):
    return AcademicService(db).update_class_subject(m, cs_id, body)


@router.get("/classes/{class_id}/allocation", response_model=ClassAllocationOut)
def class_allocation(class_id: uuid.UUID, m: CurrentMember = Depends(require_academic),
                     db: Session = Depends(get_db)):
    """Periods/week per subject vs the week's capacity, with a suggested split."""
    return AcademicService(db).class_allocation(m, class_id)


@router.put("/classes/{class_id}/allocation", response_model=ClassAllocationOut)
def set_class_allocation(class_id: uuid.UUID, body: AllocationSetIn,
                         m: CurrentMember = Depends(require_admin),
                         db: Session = Depends(get_db)):
    return AcademicService(db).set_allocation(m, class_id, body)


@router.delete("/class-subjects/{cs_id}", response_model=MessageResponse)
def delete_class_subject(cs_id: uuid.UUID, m: CurrentMember = Depends(require_admin),
                         db: Session = Depends(get_db)):
    AcademicService(db).delete_class_subject(m, cs_id)
    return MessageResponse(message="Removed.")


# ── calendar & effective teaching days (M1) ───────────────────────────────────
@router.get("/calendar/summary", response_model=CalendarSummary)
def calendar_summary(year_id: uuid.UUID, m: CurrentMember = Depends(require_academic),
                     db: Session = Depends(get_db)):
    return CalendarService(db).summary(m, year_id)


@router.get("/calendar/events", response_model=list[CalendarEventOut])
def list_events(year_id: uuid.UUID, m: CurrentMember = Depends(require_academic),
                db: Session = Depends(get_db)):
    return CalendarService(db).list_events(m, year_id)


@router.post("/calendar/events", response_model=CalendarEventOut)
def create_event(body: CalendarEventCreate, m: CurrentMember = Depends(require_admin),
                 db: Session = Depends(get_db)):
    return CalendarService(db).create_event(m, body)


@router.delete("/calendar/events/{event_id}", response_model=MessageResponse)
def delete_event(event_id: uuid.UUID, m: CurrentMember = Depends(require_admin),
                 db: Session = Depends(get_db)):
    CalendarService(db).delete_event(m, event_id)
    return MessageResponse(message="Event removed.")


@router.post("/calendar/events/bulk", response_model=list[CalendarEventOut])
def create_calendar_events(body: CalendarBulkIn, m: CurrentMember = Depends(require_admin),
                           db: Session = Depends(get_db)):
    """One round trip for a drag-selected range (V2-P7)."""
    return CalendarService(db).create_events(m, body.events)


# ── exam portions (V2-P7): what each exam actually examines ──────────────────
@router.get("/exam-portions", response_model=list[ExamPortionOut])
def list_exam_portions(class_subject_id: uuid.UUID | None = None,
                       m: CurrentMember = Depends(require_academic),
                       db: Session = Depends(get_db)):
    return ExamPortionService(db).list(m, class_subject_id)


@router.post("/exam-portions", response_model=ExamPortionOut)
def set_exam_portion(body: ExamPortionIn, m: CurrentMember = Depends(require_admin),
                     db: Session = Depends(get_db)):
    """Idempotent per (exam, class-subject) — re-posting moves the cut point."""
    return ExamPortionService(db).set(m, body)


@router.delete("/exam-portions/{portion_id}", response_model=MessageResponse)
def delete_exam_portion(portion_id: uuid.UUID, m: CurrentMember = Depends(require_admin),
                        db: Session = Depends(get_db)):
    ExamPortionService(db).delete(m, portion_id)
    return MessageResponse(message="Portion removed.")
