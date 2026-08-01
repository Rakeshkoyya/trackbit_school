"""Homework analytics schemas (HW-1)."""

import uuid
from datetime import date as date_
from datetime import datetime

from pydantic import BaseModel


class HomeworkScopeRow(BaseModel):
    """One class, subject or teacher rolled up over the window."""
    key: str                     # class label / subject name / teacher name
    id: uuid.UUID | None = None
    assigned: int                # homework set
    checked: int                 # of those, how many the teacher went through
    students_expected: int       # student-assignments covered by checked homework
    done: int
    not_done: int
    partial: int
    completion: float | None     # done / students_expected, None when nothing checked
    check_rate: float | None     # checked / assigned — the discipline number


class TeacherCheckingRow(BaseModel):
    """Is this teacher actually checking what they set?

    `unchecked_overdue` is the one that matters: homework whose due date has
    passed with no check recorded. Recently-set homework being unchecked is
    normal, and counting it would cry wolf every afternoon.
    """
    member_id: uuid.UUID | None = None
    teacher_name: str
    assigned: int
    checked: int
    unchecked_overdue: int
    check_rate: float | None
    last_checked_at: datetime | None = None


class StudentHomeworkRow(BaseModel):
    student_id: uuid.UUID
    full_name: str
    class_label: str
    roll_no: str | None = None
    assigned: int
    done: int
    not_done: int
    partial: int
    completion: float | None
    # Consecutive school days ending most-recently with a not-done result.
    streak: int = 0
    subjects: list[str] = []
    teachers: list[str] = []


class HomeworkOverview(BaseModel):
    window_days: int
    from_date: date_
    to_date: date_
    assigned: int
    checked: int
    check_rate: float | None
    overall_completion: float | None
    by_class: list[HomeworkScopeRow] = []
    by_subject: list[HomeworkScopeRow] = []
    teachers: list[TeacherCheckingRow] = []
    # Students who keep not doing it — the red list, worst first.
    needs_attention: list[StudentHomeworkRow] = []
    # Zero misses over the window, and the biggest improvers. Recognition needs a
    # list, not a single "best": in a healthy class dozens tie at zero.
    perfect: list[StudentHomeworkRow] = []
    most_improved: list[StudentHomeworkRow] = []


class StudentHomeworkItem(BaseModel):
    """One homework as it applies to one student."""
    assignment_id: uuid.UUID
    date: date_
    due_date: date_ | None = None
    subject_name: str | None = None
    class_label: str | None = None
    text: str
    personal: bool = False       # set for this student alone
    # done | not_done | partial | not_checked  — `not_checked` is the teacher's
    # gap, never the student's, and must never be presented as a miss.
    status: str
    note: str | None = None


class StudentHomeworkHistory(BaseModel):
    student_id: uuid.UUID
    full_name: str
    class_label: str | None = None
    window_days: int
    assigned: int
    done: int
    not_done: int
    partial: int
    not_checked: int
    completion: float | None
    streak: int = 0
    items: list[StudentHomeworkItem] = []
