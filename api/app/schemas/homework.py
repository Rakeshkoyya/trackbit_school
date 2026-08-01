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
    students_expected: int       # graded student-assignments — the denominator
    done: int
    not_done: int
    partial: int
    # Did it, after the deadline. Counts as done in `completion` and is reported
    # beside it, never inside it (S-99) — folding it in hides a class where
    # everything arrives four days late.
    late: int = 0
    # Absent when it was set. NOT a miss and NOT in the denominator (D-34).
    carried: int = 0
    completion: float | None     # None = nothing checked, which is not zero
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
    late: int = 0
    carried: int = 0
    completion: float | None
    # Consecutive school days ending most-recently with a miss. Days carrying
    # only a neutral verdict (not_checked / carried / waived) are skipped, never
    # counted as clean and never as a miss (S-102).
    streak: int = 0
    subjects: list[str] = []
    teachers: list[str] = []


class RoughClassRow(BaseModel):
    """D-85's second admin signal: this class WAS checked, and N children missed
    it. A different problem from "nobody checked", and a different conversation.
    """
    assignment_id: uuid.UUID
    class_label: str
    subject_name: str | None = None
    date: date_
    text: str
    missed: int
    students_expected: int
    teacher_name: str | None = None


class HomeworkOverview(BaseModel):
    window_days: int
    from_date: date_
    to_date: date_
    assigned: int
    checked: int
    check_rate: float | None
    overall_completion: float | None
    late: int = 0
    carried: int = 0
    by_class: list[HomeworkScopeRow] = []
    by_subject: list[HomeworkScopeRow] = []
    teachers: list[TeacherCheckingRow] = []
    # Students who keep not doing it — the red list, worst first.
    needs_attention: list[StudentHomeworkRow] = []
    # Zero misses over the window, and the biggest improvers. Recognition needs a
    # list, not a single "best": in a healthy class dozens tie at zero.
    perfect: list[StudentHomeworkRow] = []
    most_improved: list[StudentHomeworkRow] = []
    # The two signals D-85 sends the admin. Both are derived; neither writes
    # anything into a child's record.
    delayed_teachers: list[TeacherCheckingRow] = []
    rough_classes: list[RoughClassRow] = []


class HomeworkQueueItem(BaseModel):
    """One homework on the teacher's Homework screen (D-36 / S-101)."""
    assignment_id: uuid.UUID
    class_subject_id: uuid.UUID
    class_label: str
    subject_name: str | None = None
    date: date_
    due_date: date_ | None = None
    text: str
    student_id: uuid.UUID | None = None      # set = a personal homework
    student_name: str | None = None
    checked: bool = False
    checked_at: datetime | None = None
    # The deadline passed with nothing gone through. A fact about the RECORD —
    # never a judgement about a child, and nothing expires (D-85).
    overdue: bool = False
    days_waiting: int = 0
    missed: int = 0                          # not_done + partial on this one
    carried: int = 0                         # absent when it was set


class HomeworkQueue(BaseModel):
    from_date: date_
    to_date: date_
    items: list[HomeworkQueueItem] = []
    # S-100 — the number on the button. Without it the screen is optional.
    to_check: int = 0
    overdue: int = 0


class HomeworkLoadCell(BaseModel):
    """One class's evening: how many subjects set homework that day (D-37/S-87)."""
    class_id: uuid.UUID
    class_label: str
    date: date_
    subjects: int
    assignments: int


class HomeworkLoad(BaseModel):
    """Admin and class teacher only. Informational — no cap, no rota (D-37)."""
    from_date: date_
    to_date: date_
    cells: list[HomeworkLoadCell] = []
    busiest_class_label: str | None = None
    busiest_date: date_ | None = None
    busiest_subjects: int = 0


class StudentHomeworkItem(BaseModel):
    """One homework as it applies to one student."""
    assignment_id: uuid.UUID
    date: date_
    due_date: date_ | None = None
    subject_name: str | None = None
    class_label: str | None = None
    text: str
    personal: bool = False       # set for this student alone
    # See core/homework_verdict.py — done | late | partial | not_done | carried |
    # waived | not_checked. `not_checked` is the TEACHER's gap and `carried` is
    # an absence; neither may be presented as a miss on any surface.
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
    late: int = 0
    carried: int = 0
    waived: int = 0
    not_checked: int
    completion: float | None
    streak: int = 0
    items: list[StudentHomeworkItem] = []
