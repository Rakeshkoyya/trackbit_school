"""Director Dashboard schemas (M4, SPRD §5.4 — DB-1)."""

import uuid

from pydantic import BaseModel, Field

from app.schemas.fees import FeeSummary
from app.schemas.planner import ForecastOut
from app.schemas.sessions import SessionRecord


class HomeworkClassHealth(BaseModel):
    class_label: str
    assignments: int          # homework set in the window
    completion: float | None  # avg done/total across checks (None = no checks yet)


class HomeworkHealth(BaseModel):
    window_days: int
    overall_completion: float | None
    classes: list[HomeworkClassHealth]


class Alert(BaseModel):
    id: str                   # synthetic (computed, not stored) — for keys/prefill
    type: str                 # pace | compliance | homework
    severity: str             # amber | red
    title: str
    detail: str
    class_id: uuid.UUID | None = None
    class_subject_id: uuid.UUID | None = None


class DashboardOverview(BaseModel):
    academic_year_id: uuid.UUID | None
    rag_green: int
    rag_amber: int
    rag_red: int
    rag: list[ForecastOut]    # amber/red rows only (the ones that need attention)
    fees: FeeSummary | None   # director-only (coordinators never read fees, §3.3)
    sessions: list[SessionRecord]
    homework: HomeworkHealth
    alerts: list[Alert]


class CreateTaskFromAlert(BaseModel):
    board_id: uuid.UUID
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class DigestOut(BaseModel):
    """Monday digest (M4). In production this is delivered on the whatsapp→email
    ladder; here it's previewable. `text` is the exact message body."""
    text: str
    issues: list[str]
    wins: list[str]
