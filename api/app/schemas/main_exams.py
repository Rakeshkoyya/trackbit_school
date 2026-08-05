"""The main exams — the school's own exam calendar (founder, 2026-08-05).

A school holds two different kinds of exam and the product only ever modelled
one of them. A slip test is a thing a teacher does on a Tuesday; **the exam** is
a thing the school declares in April, sits every class for, and issues a report
card off. The second is what a parent means by "exams", and it had no surface:
`assessment_cycles` could record its marks, but nothing said which exams the
school was holding this year, and nothing tied a class's papers together.

It is not a new table. `calendar_events` with `type='exam_block'` has been the
school's exam calendar since V2-P7 — it is what the planner paces against
(`exam_fit`) and what `ExamPortion` maps chapters onto. This module gives it the
two things it never had: **a screen the admin can add and edit exams on**, and a
read of what has actually been recorded against each.

The link is `assessment_cycles.exam_event_id`, which V1-8 added (`S-115`) and
which nothing has ever populated from a screen. Recording a paper under a main
exam is therefore the SAME write as recording any other exam — one
`ExamService.save`, with the block's id on it. There is no second scores table
and no second capture surface, because a school that records the same mark twice
gets two answers to "how did he do".

Who may do what (founder):

    the exam list      admin adds, edits and removes; a teacher reads it locked
    a paper's marks    admin anywhere; a teacher **only her own subject**
    a report card      any class the teacher is assigned to, all subjects

That last line is the asymmetry that matters and it is deliberate: she must see
the whole card to talk to a parent about a child, and she must not be able to
alter a colleague's mark on it.
"""

import uuid
from datetime import date

from pydantic import BaseModel, Field


class MainExamRow(BaseModel):
    """One declared exam, with how much of it has actually been recorded.

    `recorded_subjects` of `subjects_total` is the progress figure, and it
    carries its denominator like every other figure here (ux §4). A block
    nobody has entered anything for reads *"nothing recorded yet"* — a word,
    never a bold 0%.
    """

    exam_event_id: uuid.UUID
    title: str
    start_date: date
    end_date: date
    notes: str | None = None
    affects_teaching: bool = True
    blocks_periods: list[int] | None = None
    # upcoming | running | past — decided server-side against the school's own
    # timezone, so two clients in two places cannot disagree about "today".
    state: str = "upcoming"
    days_away: int = 0
    subjects_total: int = 0
    recorded_subjects: int = 0
    locked_subjects: int = 0
    scored_students: int = 0
    classes_total: int = 0
    # Null until something is recorded. Never 0%.
    avg_pct: float | None = None
    caption: str = ""


class MainExamBoard(BaseModel):
    academic_year_id: uuid.UUID | None = None
    as_of: date
    # school = an admin, mine = a teacher's assigned classes only.
    scope: str = "school"
    # Adding, editing and removing an exam is the admin's act. A teacher gets
    # the identical board with the pencils absent — not a different screen.
    can_edit: bool = False
    rows: list[MainExamRow] = []
    headline: str = ""


class MainExamSubjectRow(BaseModel):
    """One class × subject paper of a main exam.

    `can_edit` is the SERVER's answer and the only thing the capture surface
    branches on: an admin anywhere, otherwise the teacher this class-subject is
    assigned to. Rendering the row read-only is a courtesy; the refusal lives in
    `ExamService.save`.
    """

    class_subject_id: uuid.UUID
    subject_id: uuid.UUID
    subject_name: str
    teacher_name: str | None = None
    cycle_id: uuid.UUID | None = None
    cycle_name: str | None = None
    total_marks: float | None = None
    scored: int = 0
    roster: int = 0
    avg_pct: float | None = None
    locked: bool = False
    can_edit: bool = False
    # Chapters this exam examines for this subject, if a portion was mapped —
    # read from `ExamPortion`, never a second definition of the portion.
    portion_chapters: int = 0


class MainExamClassGroup(BaseModel):
    class_id: uuid.UUID
    class_label: str
    subjects: list[MainExamSubjectRow] = []
    recorded: int = 0
    total: int = 0


class MainExamDetail(BaseModel):
    exam_event_id: uuid.UUID
    title: str
    start_date: date
    end_date: date
    notes: str | None = None
    state: str = "upcoming"
    can_edit_exam: bool = False
    classes: list[MainExamClassGroup] = []
    headline: str = ""


class MainExamIn(BaseModel):
    """Create or edit an exam block. Admin-only at the route.

    `academic_year_id` is required on create and ignored on edit — an exam does
    not move between years, and letting it would silently re-pace two calendars.
    """

    academic_year_id: uuid.UUID | None = None
    title: str = Field(min_length=1, max_length=200)
    start_date: date
    end_date: date
    notes: str | None = Field(default=None, max_length=500)
    # An exam block that does not stop teaching is a real thing (an internal
    # test held in its own period), so this is asked rather than assumed.
    affects_teaching: bool = True
    blocks_periods: list[int] | None = None
