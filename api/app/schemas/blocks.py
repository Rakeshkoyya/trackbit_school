"""Block capture schemas (TT-2) — the non-subject period's own surface.

A block reuses `sessions`' meeting, roster, media and per-student log shapes;
what is new here is the homework class's class → subject → assignment walk.
"""

import uuid
from datetime import date

from pydantic import BaseModel, Field


class SubjectOption(BaseModel):
    """One subject tab under a class tab."""

    class_subject_id: uuid.UUID
    subject_name: str
    #: How many pieces of homework are live tonight for it. Zero is shown, not
    #: hidden — "Maths · none tonight" is an answer, an absent tab is a mystery.
    open_count: int = 0


class BlockAssignment(BaseModel):
    assignment_id: uuid.UUID
    subject_name: str
    text: str
    assigned_on: date
    due_date: date | None = None
    #: True once somebody has been through it — the sheet then reports real
    #: verdicts instead of "not checked yet".
    checked: bool = False
    #: Set only for a one-child assignment.
    student_id: uuid.UUID | None = None


class BlockHomeworkOut(BaseModel):
    """Everything the homework-class screen needs for one (class, subject) tab."""

    meeting_id: uuid.UUID
    date: date
    class_id: uuid.UUID | None = None
    class_subject_id: uuid.UUID | None = None
    subjects: list[SubjectOption] = Field(default_factory=list)
    assignments: list[BlockAssignment] = Field(default_factory=list)
