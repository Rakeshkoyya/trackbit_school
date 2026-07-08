"""Daily report schemas (V2-M6, SPRD2 §5.6)."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel


class ReportHighlights(BaseModel):
    risks: list[str] = []
    ambiguities: list[str] = []
    wins: list[str] = []


class ReportSection(BaseModel):
    heading: str
    lines: list[str] = []


class DailyReportOut(BaseModel):
    id: uuid.UUID
    for_date: date
    generated_at: datetime
    status: str
    content_md: str
    highlights: ReportHighlights
    sections: list[ReportSection] = []
