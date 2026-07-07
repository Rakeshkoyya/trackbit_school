"""Fee endpoints (M6, SPRD §5.6). All gated require_office_up: director + office
only — teachers and coordinators never reach fees (SPRD §3.3 hard rule)."""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.database import get_db
from app.core.dependencies import require_office_up
from app.schemas.fees import (
    DueDateUpdate,
    FeeStructureCreate,
    FeeStructureOut,
    FeeSummary,
    OverdueStudent,
    PaymentIn,
    StudentFeeCreate,
    StudentFeeDetail,
    StudentFeeListItem,
    StudentFeeUpdate,
    TransactionOut,
)
from app.services.fees import FeeService

router = APIRouter()


# ── fee structures ───────────────────────────────────────────────────────────
@router.get("/structures", response_model=list[FeeStructureOut])
def list_structures(class_name: str | None = None, year_id: uuid.UUID | None = None,
                    m: CurrentMember = Depends(require_office_up), db: Session = Depends(get_db)):
    return FeeService(db).list_structures(m, class_name=class_name, year_id=year_id)


@router.post("/structures", response_model=FeeStructureOut)
def create_structure(body: FeeStructureCreate, m: CurrentMember = Depends(require_office_up),
                     db: Session = Depends(get_db)):
    return FeeService(db).create_structure(m, body)


@router.get("/structures/{fs_id}", response_model=FeeStructureOut)
def get_structure(fs_id: uuid.UUID, m: CurrentMember = Depends(require_office_up),
                  db: Session = Depends(get_db)):
    return FeeService(db).get_structure(m, fs_id)


# ── student fees ─────────────────────────────────────────────────────────────
@router.get("/student-fees", response_model=list[StudentFeeListItem])
def list_student_fees(
    year_id: uuid.UUID | None = None, class_name: str | None = None,
    status: str | None = None, search: str | None = Query(default=None, max_length=80),
    m: CurrentMember = Depends(require_office_up), db: Session = Depends(get_db),
):
    return FeeService(db).list_student_fees(
        m, year_id=year_id, class_name=class_name, status=status, search=search)


@router.post("/student-fees", response_model=StudentFeeDetail)
def enroll(body: StudentFeeCreate, m: CurrentMember = Depends(require_office_up),
           db: Session = Depends(get_db)):
    return FeeService(db).enroll(m, body)


@router.get("/student-fees/{sf_id}", response_model=StudentFeeDetail)
def get_student_fee(sf_id: uuid.UUID, m: CurrentMember = Depends(require_office_up),
                    db: Session = Depends(get_db)):
    return FeeService(db).get_student_fee(m, sf_id)


@router.patch("/student-fees/{sf_id}", response_model=StudentFeeDetail)
def update_discount(sf_id: uuid.UUID, body: StudentFeeUpdate,
                    m: CurrentMember = Depends(require_office_up), db: Session = Depends(get_db)):
    return FeeService(db).update_discount(m, sf_id, body)


@router.get("/student-fees/{sf_id}/transactions", response_model=list[TransactionOut])
def list_transactions(sf_id: uuid.UUID, m: CurrentMember = Depends(require_office_up),
                      db: Session = Depends(get_db)):
    return FeeService(db).list_transactions(m, sf_id)


# ── installment actions ──────────────────────────────────────────────────────
@router.post("/installments/{inst_id}/pay", response_model=StudentFeeDetail)
def pay(inst_id: uuid.UUID, body: PaymentIn, m: CurrentMember = Depends(require_office_up),
        db: Session = Depends(get_db)):
    return FeeService(db).pay(m, inst_id, body)


@router.post("/installments/{inst_id}/mark-paid", response_model=StudentFeeDetail)
def mark_paid(inst_id: uuid.UUID, m: CurrentMember = Depends(require_office_up),
              db: Session = Depends(get_db)):
    return FeeService(db).mark_paid(m, inst_id)


@router.post("/installments/{inst_id}/undo", response_model=StudentFeeDetail)
def undo(inst_id: uuid.UUID, m: CurrentMember = Depends(require_office_up),
         db: Session = Depends(get_db)):
    return FeeService(db).undo(m, inst_id)


@router.patch("/installments/{inst_id}/due-date", response_model=StudentFeeDetail)
def update_due_date(inst_id: uuid.UUID, body: DueDateUpdate,
                    m: CurrentMember = Depends(require_office_up), db: Session = Depends(get_db)):
    return FeeService(db).update_due_date(m, inst_id, body)


# ── dashboard card (M4 read-only) ────────────────────────────────────────────
@router.get("/summary", response_model=FeeSummary)
def summary(year_id: uuid.UUID | None = None, m: CurrentMember = Depends(require_office_up),
            db: Session = Depends(get_db)):
    return FeeService(db).summary(m, year_id)


@router.get("/overdue-students", response_model=list[OverdueStudent])
def overdue_students(
    year_id: uuid.UUID | None = None, limit: int = Query(20, le=100), offset: int = Query(0, ge=0),
    m: CurrentMember = Depends(require_office_up), db: Session = Depends(get_db),
):
    return FeeService(db).overdue_students(m, year_id=year_id, limit=limit, offset=offset)
