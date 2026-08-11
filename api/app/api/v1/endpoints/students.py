"""Students / guardians / categories endpoints (SPRD §4.2, screens ST-1/ST-2).

The roster is shared master data: reads are open to any active member (academics
AND fees both need it), while roster edits are coordinator/director. Fee amounts
and academic performance — the things teachers/office must not cross — live in
their own modules, not here.

**Package tiers cut this module in half** (`D-106`), along the same seam the
founder split the screens on:

- **Directory — the administration record.** Who this child is: name, guardians,
  phone, class, category. Free, and it must stay free — attendance cannot work
  without a roster, and `D-107` keeps every capture surface free in full.
- **Academics — the record the school MAKES.** The timeline, growth, the report
  card, the analysis: the record over time, which is what `pro` buys.

So the gate is per-route here rather than on the router.
"""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.database import get_db
from app.core.dependencies import (
    feature_gate,
    get_current_member,
    require_admin,
)
from app.core.features import Feature
from app.schemas.common import MessageResponse
from app.schemas.growth import StudentGrowthOut
from app.schemas.report_card import ReportCard, StudentAnalysis
from app.schemas.student_records import StudentRecordsOut
from app.schemas.students import (
    CategoryCreate,
    CategoryOut,
    CategoryUpdate,
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
from app.schemas.timeline import StudentTimelineOut
from app.services import roster_import, templates
from app.services.growth import GrowthService
from app.services.report_card import ReportCardService
from app.services.roster_import import RosterImporter
from app.services.student_records import StudentRecordsService
from app.services.students import StudentService
from app.services.timeline import StudentTimelineService

router = APIRouter()


# Declared before `/{student_id}` on purpose — FastAPI matches in order, and a
# path param would otherwise swallow "records" and 422 on the UUID parse.
#: The academic record over time — `pro` (`D-106`). The Directory routes below
#: stay free; see the module docstring for the seam.
_ACADEMICS = [Depends(feature_gate(Feature.STUDENTS_ACADEMICS))]


@router.get("/records", response_model=StudentRecordsOut, dependencies=_ACADEMICS)
def student_records(class_id: uuid.UUID | None = None,
                    q: str | None = Query(default=None, max_length=80),
                    window_days: int = Query(default=30, ge=1, le=365),
                    m: CurrentMember = Depends(get_current_member),
                    db: Session = Depends(get_db)):
    """The Academics roster — every child with attendance, exams and homework.

    Admin sees the school; a teacher sees the classes she teaches ∪ the homeroom
    she owns (`periods.visible_class_ids`), and asking for someone else's class
    is refused with a sentence rather than filtered to an empty table (`S-46`).
    """
    return StudentRecordsService(db).roster(m, class_id=class_id, query=q,
                                            window_days=window_days)


@router.get("/{student_id}/timeline", response_model=StudentTimelineOut,
            dependencies=_ACADEMICS)
def student_timeline(student_id: uuid.UUID, on_date: date | None = None,
                     m: CurrentMember = Depends(get_current_member), db: Session = Depends(get_db)):
    """§5.7 — period-by-period what the student did today (computed join, no new tables)."""
    return StudentTimelineService(db).timeline(m, student_id, on_date)


@router.get("/{student_id}/growth", response_model=StudentGrowthOut,
            dependencies=_ACADEMICS)
def student_growth(student_id: uuid.UUID, m: CurrentMember = Depends(get_current_member),
                   db: Session = Depends(get_db)):
    """Chapter-level growth report with topic drill-down. Staff-only; the service
    limits teachers to students in classes they teach (admin sees all)."""
    return GrowthService(db).growth(m, student_id)


# ── report card + analysis (V1-8, `D-81`) ────────────────────────────────────
# Two levels, deliberately: the card is numbers only; the analysis is the
# narrative over the SAME figures. Both use the growth report's access rule —
# admin any student, a teacher only students in a class they teach.
@router.get("/{student_id}/report-card", response_model=ReportCard,
            dependencies=_ACADEMICS)
def student_report_card(student_id: uuid.UUID, m: CurrentMember = Depends(get_current_member),
                        db: Session = Depends(get_db)):
    """Level 1 — the standard report card: this child's subjects and the exams
    they sat, numbers only, never a band (P4)."""
    return ReportCardService(db).for_student(m, student_id)


@router.get("/{student_id}/analysis", response_model=StudentAnalysis,
            dependencies=_ACADEMICS)
def student_analysis(student_id: uuid.UUID, m: CurrentMember = Depends(get_current_member),
                     db: Session = Depends(get_db)):
    """Level 2 — per topic, skill abilities and a per-subject narrative written
    over figures the product already computes (AI-off writes the deterministic
    version, so the page is never empty)."""
    return ReportCardService(db).analysis(m, student_id)


# ── roster xlsx import (SPRD §5.6) ───────────────────────────────────────────
@router.get("/import/template")
def import_template(_: CurrentMember = Depends(require_admin)):
    """V1-2 §6 ②: the blank template the school fills in — generated from the
    importer's own field list, so it can never drift from what commit accepts."""
    return Response(
        content=templates.roster_template(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="students-template.xlsx"'})


@router.post("/import/analyze", response_model=RosterAnalyzeOut)
async def import_analyze(file: UploadFile = File(...),
                         _: CurrentMember = Depends(require_admin)):
    return roster_import.analyze(await file.read())


@router.post("/import/commit", response_model=RosterCommitOut)
def import_commit(body: RosterCommitIn, m: CurrentMember = Depends(require_admin),
                  db: Session = Depends(get_db)):
    return RosterImporter(db).commit(
        m, mapping=body.mapping, rows=body.rows, academic_year_id=body.academic_year_id)


# ── categories ───────────────────────────────────────────────────────────────
@router.get("/categories", response_model=list[CategoryOut])
def list_categories(m: CurrentMember = Depends(get_current_member), db: Session = Depends(get_db)):
    return StudentService(db).list_categories(m)


@router.post("/categories", response_model=CategoryOut)
def create_category(body: CategoryCreate, m: CurrentMember = Depends(require_admin),
                    db: Session = Depends(get_db)):
    return StudentService(db).create_category(m, body)


@router.post("/categories/seed-defaults", response_model=list[CategoryOut])
def seed_default_categories(m: CurrentMember = Depends(require_admin),
                            db: Session = Depends(get_db)):
    return StudentService(db).ensure_default_categories(m)


@router.patch("/categories/{category_id}", response_model=CategoryOut)
def rename_category(category_id: uuid.UUID, body: CategoryUpdate,
                    m: CurrentMember = Depends(require_admin),
                    db: Session = Depends(get_db)):
    """`D-129`: renaming is safe because everything references the category by
    id. Before it, a block serving hostellers found them by matching this very
    string, so a rename here emptied every hostel roster in the school."""
    return StudentService(db).rename_category(m, category_id, body.name)


@router.delete("/categories/{category_id}", response_model=MessageResponse)
def delete_category(category_id: uuid.UUID, force: bool = False,
                    m: CurrentMember = Depends(require_admin),
                    db: Session = Depends(get_db)):
    """Refused with a 409 and the counts while the category is still in use;
    `?force=true` is the confirmed removal, which un-assigns every student on it
    and reopens every block restricted to it."""
    StudentService(db).delete_category(m, category_id, force=force)
    return MessageResponse(message="Category removed.")


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
def create_student(body: StudentCreate, m: CurrentMember = Depends(require_admin),
                   db: Session = Depends(get_db)):
    return StudentService(db).create_student(m, body)


@router.get("/{student_id}", response_model=StudentDetailOut)
def get_student(student_id: uuid.UUID, m: CurrentMember = Depends(get_current_member),
                db: Session = Depends(get_db)):
    return StudentService(db).get_student(m, student_id)


@router.patch("/{student_id}", response_model=StudentDetailOut)
def update_student(student_id: uuid.UUID, body: StudentUpdate,
                   m: CurrentMember = Depends(require_admin), db: Session = Depends(get_db)):
    return StudentService(db).update_student(m, student_id, body)


@router.delete("/{student_id}", response_model=MessageResponse)
def delete_student(student_id: uuid.UUID, m: CurrentMember = Depends(require_admin),
                   db: Session = Depends(get_db)):
    StudentService(db).delete_student(m, student_id)
    return MessageResponse(message="Student removed.")


# ── guardians ────────────────────────────────────────────────────────────────
@router.post("/{student_id}/guardians", response_model=GuardianOut)
def add_guardian(student_id: uuid.UUID, body: GuardianCreate,
                 m: CurrentMember = Depends(require_admin), db: Session = Depends(get_db)):
    return StudentService(db).add_guardian(m, student_id, body)


@router.patch("/guardians/{guardian_id}", response_model=GuardianOut)
def update_guardian(guardian_id: uuid.UUID, body: GuardianUpdate,
                    m: CurrentMember = Depends(require_admin), db: Session = Depends(get_db)):
    return StudentService(db).update_guardian(m, guardian_id, body)


@router.delete("/guardians/{guardian_id}", response_model=MessageResponse)
def delete_guardian(guardian_id: uuid.UUID, m: CurrentMember = Depends(require_admin),
                    db: Session = Depends(get_db)):
    StudentService(db).delete_guardian(m, guardian_id)
    return MessageResponse(message="Guardian removed.")
