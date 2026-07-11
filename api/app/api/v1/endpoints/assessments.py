"""Assessments & bands endpoints (M3, SPRD §5.3).

Reads: academic staff. Skill areas / cycles / verify / bands / interventions are
coordinator/director (§3.3). Band tiers never leave staff surfaces (P4)."""

import uuid

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.database import get_db
from app.core.dependencies import require_academic, require_coordinator_up
from app.schemas.assessments import (
    BandApplyIn,
    BandApplyOut,
    BandBoard,
    BandHistoryRow,
    BandSetIn,
    CaptureConfirmIn,
    CaptureCreate,
    CaptureOut,
    CaptureSummary,
    ClassAnalysis,
    CycleCreate,
    CycleOut,
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
from app.services.assessments import AssessmentService
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
@router.get("/bands", response_model=BandBoard)
def band_board(class_id: uuid.UUID, term_id: uuid.UUID | None = None,
               m: CurrentMember = Depends(require_academic), db: Session = Depends(get_db)):
    return AssessmentService(db).band_board(m, class_id, term_id)


@router.post("/bands", response_model=MessageResponse)
def set_band(body: BandSetIn, m: CurrentMember = Depends(require_coordinator_up),
             db: Session = Depends(get_db)):
    AssessmentService(db).set_band(m, body)
    return MessageResponse(message="Band set.")


# One tap after a categorization test: append the suggested tier for everyone
# whose band would move (SC-3). Admin-only, like every band write.
@router.post("/bands/apply-suggestions", response_model=BandApplyOut)
def apply_band_suggestions(body: BandApplyIn, m: CurrentMember = Depends(require_coordinator_up),
                           db: Session = Depends(get_db)):
    n = AssessmentService(db).apply_band_suggestions(m, body.class_id, body.term_id)
    return BandApplyOut(applied=n)


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
