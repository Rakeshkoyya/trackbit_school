"""Timetable schemas (V2-M3, SPRD2 §5.3)."""

import uuid
from datetime import date

from pydantic import BaseModel, Field


# ── period timing (on academic_years) ────────────────────────────────────────
class PeriodTime(BaseModel):
    start: str = Field(pattern=r"^\d{2}:\d{2}$")  # "09:00"
    end: str = Field(pattern=r"^\d{2}:\d{2}$")
    kind: str = Field(default="period", pattern="^(period|break)$")


class PeriodConfigOut(BaseModel):
    academic_year_id: uuid.UUID
    periods_per_day: int
    period_times: list[PeriodTime]


class PeriodConfigIn(BaseModel):
    academic_year_id: uuid.UUID
    periods_per_day: int = Field(ge=1, le=16)
    period_times: list[PeriodTime] = Field(default_factory=list)


# ── grid ─────────────────────────────────────────────────────────────────────
class SlotOut(BaseModel):
    id: uuid.UUID
    class_id: uuid.UUID
    weekday: int
    period_no: int
    class_subject_id: uuid.UUID
    subject_name: str | None = None
    teacher_member_id: uuid.UUID | None = None
    teacher_name: str | None = None
    effective_from: date
    effective_to: date | None = None


class Clash(BaseModel):
    """A teacher double-booked at one weekday+period across classes."""
    weekday: int
    period_no: int
    teacher_member_id: uuid.UUID
    teacher_name: str | None = None
    class_labels: list[str]


class GridOut(BaseModel):
    class_id: uuid.UUID
    class_label: str
    weekdays: list[int]
    periods_per_day: int
    slots: list[SlotOut]
    clashes: list[Clash] = Field(default_factory=list)


class SlotIn(BaseModel):
    class_id: uuid.UUID
    weekday: int = Field(ge=0, le=6)
    period_no: int = Field(ge=1, le=16)
    class_subject_id: uuid.UUID
    # Defaults to today (org tz) in the service. A mid-year edit closes the old
    # row at this date and opens the new one.
    effective_from: date | None = None


class SlotClearIn(BaseModel):
    class_id: uuid.UUID
    weekday: int = Field(ge=0, le=6)
    period_no: int = Field(ge=1, le=16)
    effective_from: date | None = None


# ── teacher views ────────────────────────────────────────────────────────────
class TeacherSlot(BaseModel):
    weekday: int
    period_no: int
    class_id: uuid.UUID
    class_label: str
    subject_name: str | None = None
    class_subject_id: uuid.UUID


class TeacherWeekOut(BaseModel):
    member_id: uuid.UUID
    weekdays: list[int]
    periods_per_day: int
    slots: list[TeacherSlot]


# ── import (photo/xlsx → parse → confirm) ─────────────────────────────────────
class ImportCell(BaseModel):
    weekday: int
    period_no: int
    class_subject_id: uuid.UUID | None = None
    subject_name: str
    confidence: float = 1.0


class ImportAnalyzeOut(BaseModel):
    class_id: uuid.UUID
    source: str  # "ai" | "fixture"
    cells: list[ImportCell]
    unmatched: list[str] = Field(default_factory=list)


class ImportCommitCell(BaseModel):
    weekday: int = Field(ge=0, le=6)
    period_no: int = Field(ge=1, le=16)
    class_subject_id: uuid.UUID


class ImportCommitIn(BaseModel):
    class_id: uuid.UUID
    effective_from: date | None = None
    cells: list[ImportCommitCell]


# ── whole-school generation (deterministic — no AI, no flag) ─────────────────
class OrgGenerateIn(BaseModel):
    academic_year_id: uuid.UUID
    effective_from: date | None = None
    # False = preview only. True = replace the live grid of every class in the
    # year with the generated one (append-only: old slots are closed, not deleted).
    apply: bool = False


class OrgDraftCell(BaseModel):
    class_id: uuid.UUID
    class_label: str
    weekday: int
    period_no: int
    class_subject_id: uuid.UUID
    subject_name: str


class OrgDraftIssue(BaseModel):
    class_label: str
    subject_name: str
    detail: str


class OrgGenerateOut(BaseModel):
    academic_year_id: uuid.UUID
    classes: int
    cells: list[OrgDraftCell]
    # Demand that could not be placed (teacher already busy / week full) — the
    # generator reports, never squeezes (§5.2 spirit).
    unplaced: list[OrgDraftIssue] = Field(default_factory=list)
    # Subjects skipped because periods_per_week is 0.
    skipped: list[OrgDraftIssue] = Field(default_factory=list)
    applied: bool = False


# ── assisted draft (flag-gated) ──────────────────────────────────────────────
class DraftOut(BaseModel):
    class_id: uuid.UUID
    enabled: bool
    cells: list[ImportCell] = Field(default_factory=list)
    clashes: list[Clash] = Field(default_factory=list)
    unresolved: list[str] = Field(default_factory=list)
    message: str
