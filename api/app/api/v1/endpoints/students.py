"""Students / guardians / categories endpoints (SPRD §4.2, screens ST-1/ST-2).

The roster is shared master data: reads are open to any active member (academics
AND fees both need it), while roster edits are coordinator/director. Fee amounts
and academic performance — the things teachers/office must not cross — live in
their own modules, not here.
"""

import uuid

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.database import get_db
from app.core.dependencies import get_current_member, require_coordinator_up
from app.schemas.common import MessageResponse
from app.schemas.students import (
    CategoryCreate,
    CategoryOut,
    GuardianCreate,
    GuardianOut,
    GuardianUpdate,
    RosterAnalyzeOut,
    RosterCommitIn,
    RosterCommitOut,
    StudentCreate,
    StudentDetailOut,
    StudentOut,
    StudentUpdate,
)
from app.services import roster_import
from app.services.roster_import import RosterImporter
from app.services.students import StudentService

router = APIRouter()


# ── roster xlsx import (SPRD §5.6) ───────────────────────────────────────────
@router.post("/import/analyze", response_model=RosterAnalyzeOut)
async def import_analyze(file: UploadFile = File(...),
                         _: CurrentMember = Depends(require_coordinator_up)):
    return roster_import.analyze(await file.read())


@router.post("/import/commit", response_model=RosterCommitOut)
def import_commit(body: RosterCommitIn, m: CurrentMember = Depends(require_coordinator_up),
                  db: Session = Depends(get_db)):
    return RosterImporter(db).commit(
        m, mapping=body.mapping, rows=body.rows, academic_year_id=body.academic_year_id)


# ── categories ───────────────────────────────────────────────────────────────
@router.get("/categories", response_model=list[CategoryOut])
def list_categories(m: CurrentMember = Depends(get_current_member), db: Session = Depends(get_db)):
    return StudentService(db).list_categories(m)


@router.post("/categories", response_model=CategoryOut)
def create_category(body: CategoryCreate, m: CurrentMember = Depends(require_coordinator_up),
                    db: Session = Depends(get_db)):
    return StudentService(db).create_category(m, body)


@router.post("/categories/seed-defaults", response_model=list[CategoryOut])
def seed_default_categories(m: CurrentMember = Depends(require_coordinator_up),
                            db: Session = Depends(get_db)):
    return StudentService(db).ensure_default_categories(m)


@router.delete("/categories/{category_id}", response_model=MessageResponse)
def delete_category(category_id: uuid.UUID, m: CurrentMember = Depends(require_coordinator_up),
                    db: Session = Depends(get_db)):
    StudentService(db).delete_category(m, category_id)
    return MessageResponse(message="Category deleted.")


# ── students ─────────────────────────────────────────────────────────────────
@router.get("", response_model=list[StudentOut])
def list_students(
    class_id: uuid.UUID | None = None,
    q: str | None = Query(default=None, max_length=80),
    m: CurrentMember = Depends(get_current_member),
    db: Session = Depends(get_db),
):
    return StudentService(db).list_students(m, class_id=class_id, query=q)


@router.post("", response_model=StudentDetailOut)
def create_student(body: StudentCreate, m: CurrentMember = Depends(require_coordinator_up),
                   db: Session = Depends(get_db)):
    return StudentService(db).create_student(m, body)


@router.get("/{student_id}", response_model=StudentDetailOut)
def get_student(student_id: uuid.UUID, m: CurrentMember = Depends(get_current_member),
                db: Session = Depends(get_db)):
    return StudentService(db).get_student(m, student_id)


@router.patch("/{student_id}", response_model=StudentDetailOut)
def update_student(student_id: uuid.UUID, body: StudentUpdate,
                   m: CurrentMember = Depends(require_coordinator_up), db: Session = Depends(get_db)):
    return StudentService(db).update_student(m, student_id, body)


@router.delete("/{student_id}", response_model=MessageResponse)
def delete_student(student_id: uuid.UUID, m: CurrentMember = Depends(require_coordinator_up),
                   db: Session = Depends(get_db)):
    StudentService(db).delete_student(m, student_id)
    return MessageResponse(message="Student removed.")


# ── guardians ────────────────────────────────────────────────────────────────
@router.post("/{student_id}/guardians", response_model=GuardianOut)
def add_guardian(student_id: uuid.UUID, body: GuardianCreate,
                 m: CurrentMember = Depends(require_coordinator_up), db: Session = Depends(get_db)):
    return StudentService(db).add_guardian(m, student_id, body)


@router.patch("/guardians/{guardian_id}", response_model=GuardianOut)
def update_guardian(guardian_id: uuid.UUID, body: GuardianUpdate,
                    m: CurrentMember = Depends(require_coordinator_up), db: Session = Depends(get_db)):
    return StudentService(db).update_guardian(m, guardian_id, body)


@router.delete("/guardians/{guardian_id}", response_model=MessageResponse)
def delete_guardian(guardian_id: uuid.UUID, m: CurrentMember = Depends(require_coordinator_up),
                    db: Session = Depends(get_db)):
    StudentService(db).delete_guardian(m, guardian_id)
    return MessageResponse(message="Guardian removed.")
