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
    notes: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _order(self) -> "CalendarEventCreate":
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date.")
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
    notes: str | None


class CalendarSummary(BaseModel):
    academic_year_id: uuid.UUID
    start_date: date
    end_date: date
    working_weekdays: list[int]
    teaching_days: int   # effective teaching days across the whole year
    events: list[CalendarEventOut]
