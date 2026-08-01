"""My Class — the class teacher's area (V1-3, D-03)."""

import uuid
from datetime import date

from pydantic import BaseModel


class MyClassSummary(BaseModel):
    class_id: uuid.UUID
    class_label: str
    roster: int = 0
    is_mine: bool = True


class MyClassOut(BaseModel):
    classes: list[MyClassSummary] = []


class RegisterCell(BaseModel):
    """One student × school day. `status` is THE day status
    (`classify_marked_day`) — the UI paints it, never re-derives. `not_marked`
    is a gap in the record and must render neutral, never red (ux §5)."""

    date: date
    # present | partial | absent | left_after_lunch | not_marked | no_school
    status: str
    late: bool = False
    # An exception reason or a covering informed-absence note (D-86: amber).
    has_reason: bool = False


class RegisterRow(BaseModel):
    student_id: uuid.UUID
    full_name: str
    roll_no: str | None = None
    cells: list[RegisterCell] = []
    # "present 18 of 21 marked school days" — the denominator is the days this
    # class actually marked, and the label must say so (ux §4).
    present_days: int = 0
    marked_days: int = 0


class RegisterOut(BaseModel):
    class_id: uuid.UUID
    class_label: str
    month: str  # YYYY-MM
    mode: str = "every_period"
    days: list[date] = []
    school_days: int = 0
    rows: list[RegisterRow] = []
