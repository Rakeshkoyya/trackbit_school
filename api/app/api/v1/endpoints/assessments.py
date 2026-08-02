"""Assessments & bands endpoints (M3, SPRD §5.3).

Reads: academic staff. Skill areas / cycles / verify / bands / interventions are
coordinator/director (§3.3). Band tiers never leave staff surfaces (P4)."""

import uuid

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.database import get_db
from app.core.dependencies import require_academic, require_admin, require_coordinator_up
from app.schemas.assessments import (
    BandConfig,
    BandHistoryRow,
    BandSetIn,
    CaptureConfirmIn,
    CaptureCreate,
    CaptureOut,
    CaptureSummary,
    ClassAnalysis,
    CycleCreate,
    CycleOut,
    ExamDetail,
    ExamLockIn,
    ExamSaveIn,
    ExamSummary,
    ExamTypeCreate,
    ExamTypeOut,
    ExamTypeUpdate,
    InterventionCreate,
    InterventionOut,
    ScoreGrid,
    ScoresBulkIn,
    SkillAreaCreate,
    SkillAreaOut,
    SkillProfile,
    SubjectTrend,
)
from app.schemas.common import MessageResponse
from app.schemas.exam_report import ExamReport
from app.schemas.report_card import ClassReportCard
from app.services.assessments import AssessmentService
from app.services.exam_report import ExamReportService
from app.services.exam_types import ExamTypeService
from app.services.exams import ExamService
from app.services.report_card import ReportCardService
from app.services.score_capture import ScoreCaptureService

router = APIRouter()


# ── skill areas ──────────────────────────────────────────────────────────────
@router.get("/skill-areas", response_model=list[SkillAreaOut])
def list_skills(m: CurrentMember = Depends(require_academic), db: Session = Depends(get_db)):
    return AssessmentService(db).list_skills(m)


@router.post("/skill-areas", response_model=SkillAreaOut)
def create_skill(body: SkillAreaCreate, m: CurrentMember = Depends(require_coordinator_up),
                 db: Session = Depends(get_db)):
    return AssessmentService(db).create_skill(m, body.name)


@router.post("/skill-areas/seed-defaults", response_model=list[SkillAreaOut])
def seed_skills(m: CurrentMember = Depends(require_coordinator_up), db: Session = Depends(get_db)):
    return AssessmentService(db).ensure_default_skills(m)


@router.delete("/skill-areas/{skill_id}", response_model=MessageResponse)
def delete_skill(skill_id: uuid.UUID, m: CurrentMember = Depends(require_coordinator_up),
                 db: Session = Depends(get_db)):
    AssessmentService(db).delete_skill(m, skill_id)
    return MessageResponse(message="Removed.")


# ── cycles ───────────────────────────────────────────────────────────────────
@router.get("/cycles", response_model=list[CycleOut])
def list_cycles(term_id: uuid.UUID | None = None, m: CurrentMember = Depends(require_academic),
                db: Session = Depends(get_db)):
    return AssessmentService(db).list_cycles(m, term_id)


# require_academic: the service lets a teacher quick-create only a class-scoped
# daily test for a class they teach; everything else stays admin-only.
@router.post("/cycles", response_model=CycleOut)
def create_cycle(body: CycleCreate, m: CurrentMember = Depends(require_academic),
                 db: Session = Depends(get_db)):
    return AssessmentService(db).create_cycle(m, body)


@router.delete("/cycles/{cycle_id}", response_model=MessageResponse)
def delete_cycle(cycle_id: uuid.UUID, m: CurrentMember = Depends(require_coordinator_up),
                 db: Session = Depends(get_db)):
    AssessmentService(db).delete_cycle(m, cycle_id)
    return MessageResponse(message="Cycle deleted.")


@router.get("/cycles/{cycle_id}/grid", response_model=ScoreGrid)
def score_grid(cycle_id: uuid.UUID, class_id: uuid.UUID,
               m: CurrentMember = Depends(require_academic), db: Session = Depends(get_db)):
    return AssessmentService(db).grid(m, cycle_id, class_id)


@router.post("/cycles/{cycle_id}/scores", response_model=MessageResponse)
def save_scores(cycle_id: uuid.UUID, body: ScoresBulkIn,
                m: CurrentMember = Depends(require_academic), db: Session = Depends(get_db)):
    AssessmentService(db).save_scores(m, cycle_id, body)
    return MessageResponse(message="Scores saved.")


@router.post("/cycles/{cycle_id}/verify", response_model=MessageResponse)
def verify_scores(cycle_id: uuid.UUID, m: CurrentMember = Depends(require_coordinator_up),
                  db: Session = Depends(get_db)):
    AssessmentService(db).verify(m, cycle_id)
    return MessageResponse(message="Verified.")


# ── exams (SC-5) — the scores screen's exam-first surface ────────────────────
# require_academic; the service scopes a teacher to classes they teach and
# keeps band tests admin-only.
@router.get("/exams", response_model=list[ExamSummary])
def exam_feed(class_id: uuid.UUID | None = None, limit: int = 30,
              m: CurrentMember = Depends(require_academic), db: Session = Depends(get_db)):
    return ExamService(db).feed(m, class_id, limit)


@router.get("/exams/{cycle_id}", response_model=ExamDetail)
def exam_detail(cycle_id: uuid.UUID, m: CurrentMember = Depends(require_academic),
                db: Session = Depends(get_db)):
    return ExamService(db).detail(m, cycle_id)


@router.post("/exams", response_model=ExamDetail)
def save_exam(body: ExamSaveIn, m: CurrentMember = Depends(require_academic),
              db: Session = Depends(get_db)):
    return ExamService(db).save(m, body)


# ── the Report tab (V1-8, D-80) ──────────────────────────────────────────────
@router.get("/exams/{cycle_id}/report", response_model=ExamReport)
def exam_report(cycle_id: uuid.UUID, m: CurrentMember = Depends(require_academic),
                db: Session = Depends(get_db)):
    """The second tab: the analysis, beside Score's bare numbers."""
    return ExamReportService(db).report(m, cycle_id)


# ── verify & lock (V1-8, D-53) ───────────────────────────────────────────────
# Lock is the teacher's own act — she marked the papers. Unlock is admin-only
# and appended with a reason (Q-62); the service enforces both.
@router.post("/exams/{cycle_id}/lock", response_model=ExamDetail)
def lock_exam(cycle_id: uuid.UUID, m: CurrentMember = Depends(require_academic),
              db: Session = Depends(get_db)):
    return ExamService(db).lock(m, cycle_id)


@router.post("/exams/{cycle_id}/unlock", response_model=ExamDetail)
def unlock_exam(cycle_id: uuid.UUID, body: ExamLockIn,
                m: CurrentMember = Depends(require_admin), db: Session = Depends(get_db)):
    return ExamService(db).unlock(m, cycle_id, body.reason)


# ── exam types (V1-8, D-55) — the school's own word ──────────────────────────
@router.get("/exam-types", response_model=list[ExamTypeOut])
def list_exam_types(include_retired: bool = False,
                    m: CurrentMember = Depends(require_academic),
                    db: Session = Depends(get_db)):
    """Seeds the pre-written nine on first read, so a teacher never has to
    configure vocabulary before recording a test."""
    return ExamTypeService(db).list(m, include_retired)


@router.post("/exam-types", response_model=ExamTypeOut)
def create_exam_type(body: ExamTypeCreate, m: CurrentMember = Depends(require_admin),
                     db: Session = Depends(get_db)):
    return ExamTypeService(db).create(m, body)


@router.patch("/exam-types/{exam_type_id}", response_model=ExamTypeOut)
def update_exam_type(exam_type_id: uuid.UUID, body: ExamTypeUpdate,
                     m: CurrentMember = Depends(require_admin), db: Session = Depends(get_db)):
    """Rename, re-scale, reorder or **retire** (never delete — an exam type that
    named forty exams last year keeps rendering on them)."""
    return ExamTypeService(db).update(m, exam_type_id, body)


# ── the class report card (V1-8, D-81 level 1) ───────────────────────────────
@router.get("/classes/{class_id}/report-card", response_model=ClassReportCard)
def class_report_card(class_id: uuid.UUID, m: CurrentMember = Depends(require_academic),
                      db: Session = Depends(get_db)):
    """*"The same thing for everybody"* — one batched read, numbers only."""
    return ReportCardService(db).for_class(m, class_id)


# ── photo score capture (SC-1) ───────────────────────────────────────────────
# require_academic throughout; the service enforces class access (admin any,
# teacher only classes they teach) and that scores land only on human confirm.
@router.post("/captures", response_model=CaptureOut)
def create_capture(body: CaptureCreate, m: CurrentMember = Depends(require_academic),
                   db: Session = Depends(get_db)):
    return ScoreCaptureService(db).create(m, body)


@router.get("/captures", response_model=list[CaptureSummary])
def list_captures(cycle_id: uuid.UUID | None = None, class_id: uuid.UUID | None = None,
                  m: CurrentMember = Depends(require_academic), db: Session = Depends(get_db)):
    return ScoreCaptureService(db).list(m, cycle_id, class_id)


@router.get("/captures/{capture_id}", response_model=CaptureOut)
def get_capture(capture_id: uuid.UUID, m: CurrentMember = Depends(require_academic),
                db: Session = Depends(get_db)):
    return ScoreCaptureService(db).get(m, capture_id)


@router.post("/captures/{capture_id}/pages", response_model=CaptureOut)
async def add_capture_page(capture_id: uuid.UUID, file: UploadFile = File(...),
                           m: CurrentMember = Depends(require_academic),
                           db: Session = Depends(get_db)):
    data = await file.read()
    return ScoreCaptureService(db).add_page(
        m, capture_id, data, file.content_type or "application/octet-stream",
        file.filename or "page.jpg")


@router.post("/captures/{capture_id}/parse", response_model=CaptureOut)
def parse_capture(capture_id: uuid.UUID, m: CurrentMember = Depends(require_academic),
                  db: Session = Depends(get_db)):
    return ScoreCaptureService(db).parse(m, capture_id)


@router.post("/captures/{capture_id}/confirm", response_model=CaptureOut)
def confirm_capture(capture_id: uuid.UUID, body: CaptureConfirmIn,
                    m: CurrentMember = Depends(require_academic), db: Session = Depends(get_db)):
    return ScoreCaptureService(db).confirm(m, capture_id, body)


@router.post("/captures/{capture_id}/discard", response_model=MessageResponse)
def discard_capture(capture_id: uuid.UUID, m: CurrentMember = Depends(require_academic),
                    db: Session = Depends(get_db)):
    ScoreCaptureService(db).discard(m, capture_id)
    return MessageResponse(message="Capture discarded.")


# ── bands ────────────────────────────────────────────────────────────────────
# V1-9: assessing a class now lives under `/bands/class` (per subject, `D-75`),
# and `/bands/apply-suggestions` + `/bands/categorize` are **deleted** — two
# implicit routes that re-banded children off whatever test happened last.


@router.post("/bands", response_model=MessageResponse)
def set_band(body: BandSetIn, m: CurrentMember = Depends(require_coordinator_up),
             db: Session = Depends(get_db)):
    """One child, by hand — the `D-70` observation route at single-child scale.
    Append-only, and the row records its source."""
    AssessmentService(db).set_band(m, body)
    return MessageResponse(message="Band set.")


# ── band config + one-tap categorization (SC-5) ──────────────────────────────
@router.get("/bands/config", response_model=BandConfig)
def band_config(m: CurrentMember = Depends(require_academic), db: Session = Depends(get_db)):
    return AssessmentService(db).band_config(m)


@router.put("/bands/config", response_model=BandConfig)
def set_band_config(body: BandConfig, m: CurrentMember = Depends(require_admin),
                    db: Session = Depends(get_db)):
    return AssessmentService(db).set_band_config(m, body)


# student_id -> current tier for the whole org — staff-only directory chips (P4).
@router.get("/bands/current", response_model=dict)
def current_bands(m: CurrentMember = Depends(require_academic), db: Session = Depends(get_db)):
    return AssessmentService(db).current_band_map(m)


# ── student profile ──────────────────────────────────────────────────────────
@router.get("/students/{student_id}/bands", response_model=list[BandHistoryRow])
def band_history(student_id: uuid.UUID, m: CurrentMember = Depends(require_academic),
                 db: Session = Depends(get_db)):
    return AssessmentService(db).band_history(m, student_id)


@router.get("/students/{student_id}/skill-profile", response_model=SkillProfile)
def skill_profile(student_id: uuid.UUID, m: CurrentMember = Depends(require_academic),
                  db: Session = Depends(get_db)):
    return AssessmentService(db).skill_profile(m, student_id)


@router.get("/students/{student_id}/interventions", response_model=list[InterventionOut])
def student_interventions(student_id: uuid.UUID, m: CurrentMember = Depends(require_academic),
                          db: Session = Depends(get_db)):
    return AssessmentService(db).student_interventions(m, student_id)


# ── trends + interventions ───────────────────────────────────────────────────
@router.get("/classes/{class_id}/trends", response_model=list[SubjectTrend])
def trends(class_id: uuid.UUID, m: CurrentMember = Depends(require_academic),
           db: Session = Depends(get_db)):
    return AssessmentService(db).trends(m, class_id)


@router.get("/classes/{class_id}/analysis", response_model=ClassAnalysis)
def class_analysis(class_id: uuid.UUID, m: CurrentMember = Depends(require_academic),
                   db: Session = Depends(get_db)):
    return AssessmentService(db).class_analysis(m, class_id)


@router.post("/interventions", response_model=InterventionOut)
def create_intervention(body: InterventionCreate, m: CurrentMember = Depends(require_coordinator_up),
                        db: Session = Depends(get_db)):
    return AssessmentService(db).create_intervention(m, body)
