"""Daily report schemas (V2-M6, SPRD2 §5.6)."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel


class ReportHighlights(BaseModel):
    risks: list[str] = []
    ambiguities: list[str] = []
    wins: list[str] = []
    # The 2-3 sentence headline the dashboard leads with; every section stays
    # folded behind "More". `summary_source` is 'ai' or 'fixture'.
    summary: str = ""
    summary_source: str = "fixture"


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
