"""Lucy's operating-board tools (DASH3 §6).

Every board the admin can open, the admin can also just *ask for*. These are
thin wrappers over `services/insights/*` with the real `CurrentMember` passed
through, so the boards' own scoping does the guarding — and all of them are
`role="admin"`, matching the tabs themselves: the board names every teacher's
pace and lists students by name, and none of that is a teacher's to read.

Read tools only. The action rail stays out of chat on purpose: reminding a
guardian and assigning cover are decisions with a person on the other end, and
the confirm surface for them is the red row itself, where the admin can see who
they are about to message and whether someone already did.
"""

import uuid
from datetime import date

from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.services.insights.attendance import AttendanceInsights
from app.services.insights.exams import ExamInsights
from app.services.insights.homework import HomeworkInsights
from app.services.insights.syllabus import SyllabusInsights
from app.services.insights.tasks import TaskInsights
from app.services.insights.workload import WorkloadInsights
from app.services.lucy.registry import tool

_UUID = {"type": "string", "format": "uuid"}
_DATE = {"type": "string", "format": "date",
         "description": "ISO date YYYY-MM-DD; omit for today"}


@tool("get_absence_streaks",
      "Students absent for EVERY marked period of N consecutive school days, with "
      "their class, the class teacher, and whether a guardian was already reminded "
      "today. This is the answer to 'who has been missing school?'.",
      params={"min_days": {"type": "integer",
                           "description": "streak threshold, default 3"}},
      role="admin", widgets=("table", "alert_list"), default_widget="table")
def get_absence_streaks(m: CurrentMember, db: Session, min_days: int = 3):
    return AttendanceInsights(db).streaks(m, min_days)


@tool("get_capture_grid",
      "Class × period grid for one day showing which periods were actually MARKED. "
      "Use when asked whether attendance was taken — it separates 'attendance is "
      "bad' from 'attendance was never taken', which a percentage cannot.",
      params={"on_date": _DATE},
      role="admin", widgets=("roster_grid", "table"), default_widget="table")
def get_capture_grid(m: CurrentMember, db: Session, on_date: date | None = None):
    return AttendanceInsights(db).capture_grid(m, on_date)


@tool("get_staff_board",
      "Staff right now and this week: who is present/away/on leave, which period is "
      "running and who is teaching, working or free in it, the pending leave queue, "
      "and teaching load per teacher against the school mean.",
      role="admin", widgets=("stat_group", "table"), default_widget="stat_group")
def get_staff_board(m: CurrentMember, db: Session):
    return WorkloadInsights(db).staff_board(m)


@tool("get_absence_impact",
      "What ONE absent staff member's day breaks: the periods they were due to "
      "teach, who is already covering, and the ranked list of teachers genuinely "
      "free to cover each one. Needs a member_id from get_staff_board.",
      params={"member_id": {**_UUID, "required": True}, "on_date": _DATE},
      role="admin", widgets=("table", "timeline"))
def get_absence_impact(m: CurrentMember, db: Session, member_id: uuid.UUID,
                       on_date: date | None = None):
    return AttendanceInsights(db).staff_impact(m, member_id, on_date)


@tool("get_syllabus_board",
      "Syllabus coverage against plan, pivoted: scope=class|subject|teacher, "
      "checkpoint=year|term|exam. Returns pace per node plus every class-subject "
      "row. Note 'unplanned'/'unallocated' are STATES, not a rating — report them "
      "as themselves, never as behind.",
      params={
          "scope": {"type": "string", "enum": ["school", "class", "subject", "teacher"],
                    "description": "default 'class'"},
          "checkpoint": {"type": "string", "enum": ["year", "term", "exam"],
                         "description": "default 'year'"},
          "term_id": _UUID,
      },
      role="admin", row_cap=80, widgets=("table", "rag_board"), default_widget="table")
def get_syllabus_board(m: CurrentMember, db: Session, scope: str = "class",
                       checkpoint: str = "year", term_id: uuid.UUID | None = None):
    return SyllabusInsights(db).board(m, None, scope, checkpoint, term_id)


@tool("get_homework_board",
      "Homework: the set -> checked -> done funnel (all three in student-homeworks, "
      "so they nest), completion by class, by subject and by class-subject cell, "
      "which teachers are actually checking what they set, students who keep "
      "missing it, and the trend. Completion is over what has a VERDICT, never "
      "over what was given: 'not_checked' is the teacher's gap and is never a "
      "student's miss, and 'carried' (absent when it was set) and 'waived' leave "
      "the denominator entirely.",
      params={"window_days": {"type": "integer", "description": "default 14"}},
      role="admin", widgets=("table", "stat_group"))
def get_homework_board(m: CurrentMember, db: Session, window_days: int = 14):
    return HomeworkInsights(db).board(m, window_days)


@tool("get_task_board",
      "Assigned-task health (open/overdue/critical, by board and by person) plus "
      "today's classroom duties per teacher — attendance marked, lesson logged, "
      "homework set, checks confirmed — against the periods they were due to teach.",
      params={"window_days": {"type": "integer", "description": "default 14"}},
      role="admin", widgets=("table", "stat_group"))
def get_task_board(m: CurrentMember, db: Session, window_days: int = 14):
    return TaskInsights(db).board(m, window_days)


@tool("get_exams_board",
      "Test results school-wide: average by class and by subject, per-subject "
      "trajectories across cycles, score distribution and recent tests with "
      "participation. Filter by cycle type (chapter_test, class_test, slip_test, "
      "objective, band_test, term exams).",
      params={"type": {"type": "string", "description": "assessment cycle type"}},
      role="admin", row_cap=60, widgets=("table", "line", "bar"), default_widget="table")
def get_exams_board(m: CurrentMember, db: Session, type: str | None = None):
    return ExamInsights(db).board(m, None, type)
