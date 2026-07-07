"""Syllabus + plan + forecast schemas (M1, SPRD §5.1)."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


# ── syllabus ─────────────────────────────────────────────────────────────────
class TopicOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    title: str
    est_periods: int
    position: int


class UnitOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    title: str
    position: int
    topics: list[TopicOut] = Field(default_factory=list)


class UnitCreate(BaseModel):
    class_subject_id: uuid.UUID
    title: str = Field(min_length=1, max_length=200)


class TopicCreate(BaseModel):
    unit_id: uuid.UUID
    title: str = Field(min_length=1, max_length=200)
    est_periods: int = Field(default=1, ge=1, le=40)


class SplitIn(BaseModel):
    text: str = Field(min_length=1, max_length=20000)


class SplitUnit(BaseModel):
    title: str
    topics: list[str]


class SplitOut(BaseModel):
    units: list[SplitUnit]


# ── plan + forecast ──────────────────────────────────────────────────────────
class PlanEntryOut(BaseModel):
    topic_id: uuid.UUID
    topic_title: str
    unit_title: str
    week_start: date


class PlanOut(BaseModel):
    class_subject_id: uuid.UUID
    status: str  # draft | approved | none
    approved_at: datetime | None = None
    total_est_periods: int
    entries: list[PlanEntryOut]


class ForecastOut(BaseModel):
    class_subject_id: uuid.UUID
    subject_name: str
    class_label: str
    status: str  # rag: green | amber | red | none
    total_topics: int
    baseline_finish: date | None = None
    projected_finish: date | None = None
    weeks_behind: int = 0
