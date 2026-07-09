"""Calendar / effective-days schemas (M1, SPRD §4.3 / §5.1)."""

import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict, Field, model_validator

EVENT_TYPES = "^(holiday|exam_block|event|celebration)$"


class CalendarEventCreate(BaseModel):
    academic_year_id: uuid.UUID
    type: str = Field(pattern=EVENT_TYPES)
    title: str = Field(min_length=1, max_length=200)
    start_date: date
    end_date: date
    affects_teaching: bool = True
    # Periods this event eats, e.g. [1,2,3] for a morning exam. Omit/null for a
    # whole-day event — the planner then removes the day entirely (V2-P7).
    blocks_periods: list[int] | None = None
    notes: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _order(self) -> "CalendarEventCreate":
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date.")
        if self.blocks_periods is not None:
            if not self.blocks_periods:
                raise ValueError("blocks_periods must be null (whole day) or non-empty.")
            if any(p < 1 for p in self.blocks_periods):
                raise ValueError("blocks_periods entries are 1-based period numbers.")
        return self


class CalendarEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    academic_year_id: uuid.UUID
    type: str
    title: str
    start_date: date
    end_date: date
    affects_teaching: bool
    blocks_periods: list[int] | None = None
    notes: str | None


class CalendarBulkIn(BaseModel):
    """Painting a week on the drag-select grid must not be seven round trips."""
    events: list[CalendarEventCreate] = Field(min_length=1, max_length=200)


class CalendarSummary(BaseModel):
    academic_year_id: uuid.UUID
    start_date: date
    end_date: date
    working_weekdays: list[int]
    teaching_days: int   # effective teaching days across the whole year
    events: list[CalendarEventOut]


# ── exam portions (V2-P7, SPRD2 §5.2) ────────────────────────────────────────
class ExamPortionIn(BaseModel):
    """Says: this exam covers that class-subject up to and including this topic."""
    exam_event_id: uuid.UUID
    class_subject_id: uuid.UUID
    upto_topic_id: uuid.UUID


class ExamPortionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    exam_event_id: uuid.UUID
    class_subject_id: uuid.UUID
    upto_topic_id: uuid.UUID
