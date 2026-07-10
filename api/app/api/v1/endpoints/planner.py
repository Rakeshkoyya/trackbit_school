"""Syllabus + plan + forecast endpoints (M1, SPRD §5.1).

Reads: academic staff. Structural writes: coordinator/director. Plan approval
(baseline lock) is director-only (SPRD §3.3)."""

import uuid

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.database import get_db
from app.core.dependencies import require_academic, require_admin, require_coordinator_up
from app.schemas.common import MessageResponse
from app.schemas.ingest import (
    SyllabusAnalyzeOut,
    SyllabusCommitIn,
    SyllabusCommitOut,
    SyllabusTextIn,
)
from app.schemas.periods import TopicProgressRow
from app.schemas.planner import (
    ForecastOut,
    PlanCommentIn,
    PlanCommentOut,
    PlanGenerateOut,
    PlanOut,
    SplitIn,
    SplitOut,
    TopicCreate,
    TopicEstimateIn,
    TopicOut,
    UnitCreate,
    UnitOut,
)
from app.services.planner import PlannerService
from app.services.syllabus_import import SyllabusImporter, analyze_file, analyze_text

router = APIRouter()


# ── syllabus ─────────────────────────────────────────────────────────────────
@router.get("/syllabus", response_model=list[UnitOut])
def get_syllabus(class_subject_id: uuid.UUID, m: CurrentMember = Depends(require_academic),
                 db: Session = Depends(get_db)):
    return PlannerService(db).get_syllabus(m, class_subject_id)


@router.post("/syllabus/units", response_model=UnitOut)
def add_unit(body: UnitCreate, m: CurrentMember = Depends(require_coordinator_up),
             db: Session = Depends(get_db)):
    return PlannerService(db).add_unit(m, body.class_subject_id, body.title, body.term_id)


@router.post("/syllabus/topics", response_model=TopicOut)
def add_topic(body: TopicCreate, m: CurrentMember = Depends(require_coordinator_up),
              db: Session = Depends(get_db)):
    return PlannerService(db).add_topic(m, body.unit_id, body.title, body.est_periods)


@router.put("/syllabus/topics/{topic_id}/estimate", response_model=TopicOut)
def set_topic_estimate(topic_id: uuid.UUID, body: TopicEstimateIn,
                       m: CurrentMember = Depends(require_coordinator_up),
                       db: Session = Depends(get_db)):
    """Size a chapter when its term begins — the whole point of term-wise planning."""
    return PlannerService(db).set_topic_estimate(m, topic_id, body.est_periods)


@router.delete("/syllabus/units/{unit_id}", response_model=MessageResponse)
def delete_unit(unit_id: uuid.UUID, m: CurrentMember = Depends(require_coordinator_up),
                db: Session = Depends(get_db)):
    PlannerService(db).delete_unit(m, unit_id)
    return MessageResponse(message="Chapter removed.")


@router.delete("/syllabus/topics/{topic_id}", response_model=MessageResponse)
def delete_topic(topic_id: uuid.UUID, m: CurrentMember = Depends(require_coordinator_up),
                 db: Session = Depends(get_db)):
    PlannerService(db).delete_topic(m, topic_id)
    return MessageResponse(message="Topic removed.")


@router.post("/syllabus/split", response_model=SplitOut)
def split_syllabus(body: SplitIn, _: CurrentMember = Depends(require_coordinator_up),
                   db: Session = Depends(get_db)):
    return SplitOut(units=PlannerService(db).split_text(body.text))


# ── syllabus document import (V2-P7, SPRD2 §5.1) ─────────────────────────────
@router.post("/syllabus/import/analyze", response_model=SyllabusAnalyzeOut)
async def syllabus_import_analyze(file: UploadFile = File(...),
                                  _: CurrentMember = Depends(require_coordinator_up)):
    """xlsx/csv grid, a typed-out list, or a PDF/photo of a printed syllabus (read by
    the multimodal model). All three come back as the same editable draft."""
    return analyze_file(await file.read(), file.filename or "syllabus.xlsx")


@router.post("/syllabus/import/text", response_model=SyllabusAnalyzeOut)
def syllabus_import_text(body: SyllabusTextIn,
                         _: CurrentMember = Depends(require_coordinator_up)):
    """Paste path. Same draft shape as the file path, so the UI has one review screen."""
    return analyze_text(body.text)


@router.post("/syllabus/import/commit", response_model=SyllabusCommitOut)
def syllabus_import_commit(body: SyllabusCommitIn,
                           m: CurrentMember = Depends(require_coordinator_up),
                           db: Session = Depends(get_db)):
    return SyllabusImporter(db).commit(
        m, class_subject_id=body.class_subject_id,
        units=[u.model_dump() for u in body.units], replace=body.replace)


# ── plan ─────────────────────────────────────────────────────────────────────
@router.get("/plan", response_model=PlanOut)
def get_plan(class_subject_id: uuid.UUID, m: CurrentMember = Depends(require_academic),
             db: Session = Depends(get_db)):
    return PlannerService(db).get_plan(m, class_subject_id)


@router.get("/plan/forecast", response_model=list[ForecastOut])
def plan_forecast(class_id: uuid.UUID, m: CurrentMember = Depends(require_academic),
                  db: Session = Depends(get_db)):
    return PlannerService(db).forecast(m, class_id)


@router.post("/plan/{cs_id}/draft", response_model=PlanOut)
def draft_plan(cs_id: uuid.UUID, term_id: uuid.UUID | None = None,
               m: CurrentMember = Depends(require_coordinator_up),
               db: Session = Depends(get_db)):
    """`term_id` scopes the draft to one term; omit it to plan the whole year."""
    return PlannerService(db).draft_plan(m, cs_id, term_id)


@router.get("/plan/{cs_id}/progress", response_model=list[TopicProgressRow])
def topic_progress(cs_id: uuid.UUID, m: CurrentMember = Depends(require_academic),
                   db: Session = Depends(get_db)):
    """Chapter/topic progress computed from lesson logs (P2) — what the period card
    shows as done / in progress / pending."""
    return PlannerService(db).topic_progress(m, cs_id)


@router.post("/plan/{cs_id}/generate", response_model=PlanGenerateOut)
def generate_plan(cs_id: uuid.UUID, term_id: uuid.UUID | None = None,
                  m: CurrentMember = Depends(require_coordinator_up),
                  db: Session = Depends(get_db)):
    """Proposer + deterministic validators (V2-M2 §5.2). Over-capacity is reported.
    `term_id` scopes generation to one term, leaving other terms' baselines alone."""
    return PlannerService(db).generate_plan(m, cs_id, term_id)


@router.post("/plan/{cs_id}/approve", response_model=PlanOut)
def approve_plan(cs_id: uuid.UUID, term_id: uuid.UUID | None = None,
                 m: CurrentMember = Depends(require_admin),
                 db: Session = Depends(get_db)):
    """Lock a baseline (P2). `term_id` locks just that term; omit it to lock the year."""
    return PlannerService(db).approve_plan(m, cs_id, term_id)


@router.post("/plan/{cs_id}/unapprove", response_model=PlanOut)
def unapprove_plan(cs_id: uuid.UUID, term_id: uuid.UUID | None = None,
                   m: CurrentMember = Depends(require_admin),
                   db: Session = Depends(get_db)):
    """Unlock a baseline so it can be re-planned. Appends a compensating row to
    `plan_approvals` — the approval history is never rewritten (law 3)."""
    return PlannerService(db).unapprove_plan(m, cs_id, term_id)


# ── teacher change-requests (comment threads on the plan, §5.2) ───────────────
@router.get("/plan/{cs_id}/comments", response_model=list[PlanCommentOut])
def list_comments(cs_id: uuid.UUID, include_resolved: bool = False,
                  m: CurrentMember = Depends(require_academic), db: Session = Depends(get_db)):
    return PlannerService(db).list_comments(m, cs_id, include_resolved)


@router.post("/plan/{cs_id}/comments", response_model=PlanCommentOut)
def add_comment(cs_id: uuid.UUID, body: PlanCommentIn,
                m: CurrentMember = Depends(require_academic), db: Session = Depends(get_db)):
    return PlannerService(db).add_comment(m, cs_id, body)


@router.post("/plan/comments/{comment_id}/resolve", response_model=PlanCommentOut)
def resolve_comment(comment_id: uuid.UUID, m: CurrentMember = Depends(require_coordinator_up),
                    db: Session = Depends(get_db)):
    return PlannerService(db).resolve_comment(m, comment_id)
