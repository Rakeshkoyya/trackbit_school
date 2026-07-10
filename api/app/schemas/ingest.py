"""Document-ingestion schemas (V2-P7, SPRD2 §5.1/§8).

The analyze envelope is the same for every importer. `questions` are phrased by the
model but *found* by deterministic validators, so this response is identical with or
without an API key — only the wording changes."""

import uuid
from typing import Any

from pydantic import BaseModel, Field


class GapQuestion(BaseModel):
    field: str
    label: str
    question: str
    options: list[str] = []
    skippable: bool = True
    source: str = "fixture"  # "ai" when a key is configured


class AnalyzeOut(BaseModel):
    columns: list[str] = []
    mapping: dict[str, str] = {}
    rows: list[dict[str, Any]] = []
    row_count: int = 0
    unmapped_columns: list[str] = []
    missing_required: list[str] = []
    low_confidence: list[str] = []
    questions: list[GapQuestion] = []
    source: str = "heuristic"


# ── staff ────────────────────────────────────────────────────────────────────
class StaffCommitIn(BaseModel):
    mapping: dict[str, str]
    rows: list[dict[str, Any]] = Field(min_length=1, max_length=500)
    academic_year_id: uuid.UUID | None = None
    # When set, every imported teacher gets this password (they must change it on
    # first login). Otherwise each gets a random one, echoed back once.
    default_password: str | None = Field(default=None, min_length=8, max_length=128)


class StaffCreated(BaseModel):
    name: str
    username: str
    password: str
    user_id: str


class StaffCommitOut(BaseModel):
    created: list[StaffCreated] = []
    created_count: int = 0
    skipped: int = 0
    assigned: int = 0
    errors: list[dict[str, Any]] = []
    # Assignment hints we refused to guess at — the admin resolves these by hand.
    unresolved: list[dict[str, Any]] = []


# ── syllabus ─────────────────────────────────────────────────────────────────
class SyllabusTopicDraft(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    est_periods: int = Field(default=1, ge=1, le=200)


class SyllabusUnitDraft(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    topics: list[SyllabusTopicDraft] = []


class SyllabusAnalyzeOut(AnalyzeOut):
    mode: str = "grid"  # grid | text
    units: list[SyllabusUnitDraft] = []
    unit_count: int = 0
    topic_count: int = 0


class SyllabusTextIn(BaseModel):
    text: str = Field(min_length=1, max_length=200_000)


class SyllabusCommitIn(BaseModel):
    class_subject_id: uuid.UUID
    units: list[SyllabusUnitDraft] = Field(min_length=1, max_length=200)
    # True wipes the existing syllabus first — the "re-import, I got it wrong" path.
    replace: bool = False


class SyllabusCommitOut(BaseModel):
    units_created: int
    topics_created: int
    replaced: bool
    # Chapters imported without a period estimate — they are recorded but not
    # schedulable until someone sizes them.
    unsized_topics: int = 0
    # Term names in the sheet that matched no term of this class's academic year.
    unresolved_terms: list[str] = Field(default_factory=list)
