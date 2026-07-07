"""Assessments & bands endpoints (M3, SPRD §5.3).

Reads: academic staff. Skill areas / cycles / verify / bands / interventions are
coordinator/director (§3.3). Band tiers never leave staff surfaces (P4)."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.database import get_db
from app.core.dependencies import require_academic, require_coordinator_up
from app.schemas.assessments import (
    BandBoard,
    BandHistoryRow,
    BandSetIn,
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


@router.post("/cycles", response_model=CycleOut)
def create_cycle(body: CycleCreate, m: CurrentMember = Depends(require_coordinator_up),
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


@router.post("/interventions", response_model=InterventionOut)
def create_intervention(body: InterventionCreate, m: CurrentMember = Depends(require_coordinator_up),
                        db: Session = Depends(get_db)):
    return AssessmentService(db).create_intervention(m, body)
