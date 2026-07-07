"""Syllabus + plan + forecast endpoints (M1, SPRD §5.1).

Reads: academic staff. Structural writes: coordinator/director. Plan approval
(baseline lock) is director-only (SPRD §3.3)."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.database import get_db
from app.core.dependencies import require_academic, require_admin, require_coordinator_up
from app.schemas.common import MessageResponse
from app.schemas.planner import (
    ForecastOut,
    PlanOut,
    SplitIn,
    SplitOut,
    TopicCreate,
    TopicOut,
    UnitCreate,
    UnitOut,
)
from app.services.planner import PlannerService

router = APIRouter()


# ── syllabus ─────────────────────────────────────────────────────────────────
@router.get("/syllabus", response_model=list[UnitOut])
def get_syllabus(class_subject_id: uuid.UUID, m: CurrentMember = Depends(require_academic),
                 db: Session = Depends(get_db)):
    return PlannerService(db).get_syllabus(m, class_subject_id)


@router.post("/syllabus/units", response_model=UnitOut)
def add_unit(body: UnitCreate, m: CurrentMember = Depends(require_coordinator_up),
             db: Session = Depends(get_db)):
    return PlannerService(db).add_unit(m, body.class_subject_id, body.title)


@router.post("/syllabus/topics", response_model=TopicOut)
def add_topic(body: TopicCreate, m: CurrentMember = Depends(require_coordinator_up),
              db: Session = Depends(get_db)):
    return PlannerService(db).add_topic(m, body.unit_id, body.title, body.est_periods)


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
def draft_plan(cs_id: uuid.UUID, m: CurrentMember = Depends(require_coordinator_up),
               db: Session = Depends(get_db)):
    return PlannerService(db).draft_plan(m, cs_id)


@router.post("/plan/{cs_id}/approve", response_model=PlanOut)
def approve_plan(cs_id: uuid.UUID, m: CurrentMember = Depends(require_admin),
                 db: Session = Depends(get_db)):
    return PlannerService(db).approve_plan(m, cs_id)
