"""The teacher-facing syllabus contracts (V1-6 — `S-46`, `D-10`, `D-15`).

Deliberately a different shape from `SyllabusBoard`. The admin arrives asking
*"who is falling behind?"* and needs pivots, ranks and a school total; a teacher
arrives asking *"where am I, and what do I teach next?"* and needs a list. Five
to eight rows is a list, not a selector — which is the whole of `S-46`.
"""

import uuid
from datetime import date as date_

from pydantic import BaseModel


class SubjectPaceRow(BaseModel):
    """One class-subject, from the point of view of whoever teaches it.

    `next_topic_title` is the field the screen exists for: it is the reason she
    opened it, and before V1-6 it took four clicks through a dropdown maze to
    reach. `status` has already been through `core.coverage.rated_status`, so a
    subject she has not logged reads **unknown** rather than accusing her of
    being three weeks behind on evidence nobody recorded (`S-42`).
    """

    class_subject_id: uuid.UUID
    class_id: uuid.UUID
    class_label: str
    subject_id: uuid.UUID | None = None
    subject_name: str
    status: str

    # Both denominators (`S-51`) — "will we finish?" and "are we on pace?".
    taught_topics: float = 0
    planned_topics: int = 0
    total_topics: int = 0
    coverage_pct: float | None = None
    syllabus_pct: float | None = None

    due_topics: int = 0
    behind_topics: float = 0
    weeks_behind: int = 0
    unestimated_topics: int = 0
    logged_periods: int = 0

    next_topic_title: str | None = None
    next_chapter_title: str | None = None
    last_taught_on: date_ | None = None

    # Only populated on the class teacher's view (`D-15`) — she sees all
    # subjects and all teachers' pace, but only for her own class. Never
    # school-wide, and never a rank.
    teacher_name: str | None = None
    cause: str | None = None
    cause_detail: str | None = None


class MySubjectsOut(BaseModel):
    academic_year_id: uuid.UUID | None = None
    as_of: date_
    headline: str
    rows: list[SubjectPaceRow] = []


class ClassSyllabusOut(BaseModel):
    class_id: uuid.UUID
    class_label: str
    as_of: date_
    headline: str
    rows: list[SubjectPaceRow] = []
