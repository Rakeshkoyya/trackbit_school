"""Lucy's write tools — all `confirm=True`, so the agent can only PROPOSE.

The loop files each call as a pending action; the human taps Confirm in the
chat (or it expires), and only then does `LucyService.confirm_action` run the
handler — with the member's real authority, through the same services as the
buttons in the UI. That pending-action card IS the human-confirm surface the
AI doctrine requires, and the action rows are an append-only audit (law 3).

Every write here is idempotent-or-additive at the service layer already
(attendance mark = full-replace of the exception set, homework/logs/comments
are inserts, task creation is event-sourced).

Deliberately NOT here yet (extend the registry when the UX exists):
fee payments (money — needs a stronger double-confirm), band changes,
exam/score entry, student enrolment, calendar edits, and ANYTHING that
messages guardians (P4: band tiers must never leak to parents).
"""

import uuid
from datetime import UTC, date, datetime, time

from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.schemas.attendance import AttendanceMarkIn
from app.schemas.checks import CheckConfirmIn
from app.schemas.classroom import HomeworkIn, LessonLogIn
from app.schemas.planner import PlanCommentIn
from app.schemas.task import TaskCreateRequest
from app.services.attendance import AttendanceService
from app.services.board import BoardService
from app.services.classroom import ClassroomService
from app.services.lucy.registry import tool
from app.services.planner import PlannerService
from app.services.recommendations import RecommendationsService
from app.services.task import TaskService

_UUID = {"type": "string", "format": "uuid"}
_DATE = {"type": "string", "format": "date",
         "description": "ISO date YYYY-MM-DD; omit for today"}
_SUMMARY = {"type": "string",
            "description": "REQUIRED: one plain sentence describing exactly what "
                           "will happen, shown on the user's confirm card"}


@tool("list_task_boards",
      "The task boards this user can see (id + name). Needed before create_task.",
      widgets=("table",))
def list_task_boards(m: CurrentMember, db: Session):
    data = BoardService(db).list_boards(m).model_dump(mode="json")
    return [{"id": b.get("id"), "name": b.get("name"), "mine": mine}
            for rows, mine in ((data.get("my_boards", []), True),
                               (data.get("other_public", []), False))
            for b in rows if isinstance(b, dict)]


@tool("create_task",
      "Create a task on a board (e.g. turn a problem you found into a follow-up). "
      "Get the board_id from list_task_boards first.",
      params={"board_id": {**_UUID, "required": True},
              "title": {"type": "string", "required": True},
              "description": {"type": "string"},
              "due_date": _DATE,
              "priority": {"type": "integer", "description": "0 none … 3 high"},
              "summary": _SUMMARY},
      kind="write", confirm=True)
def create_task(m: CurrentMember, db: Session, board_id: uuid.UUID, title: str,
                description: str | None = None, due_date: date | None = None,
                priority: int = 0):
    req = TaskCreateRequest(
        board_id=board_id, title=title, description=description,
        priority=max(0, min(3, priority)),
        due_at=datetime.combine(due_date, time(12, 0), UTC) if due_date else None,
        all_day=due_date is not None)
    return TaskService(db).create(m, req)


@tool("mark_attendance",
      "Mark one class-period's attendance by exception: everyone is present "
      "EXCEPT the students you list as absent/late. An empty exceptions list "
      "means all present. Replaces the period's previous exception set.",
      params={"class_id": {**_UUID, "required": True},
              "period_no": {"type": "integer", "required": True},
              "on_date": _DATE,
              "exceptions": {
                  "type": "array", "required": True,
                  "description": "the deviations only",
                  "items": {"type": "object", "properties": {
                      "student_id": {"type": "string", "format": "uuid"},
                      "status": {"type": "string", "enum": ["absent", "late"]},
                      "late_minutes": {"type": "integer"}},
                      "required": ["student_id", "status"]}},
              "summary": _SUMMARY},
      kind="write", confirm=True)
def mark_attendance(m: CurrentMember, db: Session, class_id: uuid.UUID,
                    period_no: int, exceptions: list,
                    on_date: date | None = None):
    body = AttendanceMarkIn(class_id=class_id, period_no=period_no,
                            date=on_date, exceptions=exceptions)
    return AttendanceService(db).mark(m, body)


@tool("log_lesson",
      "Log what was taught in a class-subject (topic from the syllabus and/or a "
      "free note). Use get_class_subjects for the class_subject_id.",
      params={"class_subject_id": {**_UUID, "required": True},
              "note": {"type": "string"},
              "topic_id": {**_UUID, "description": "syllabus topic that was taught"},
              "coverage": {"type": "string", "enum": ["full", "partial"]},
              "period_no": {"type": "integer"},
              "on_date": _DATE,
              "summary": _SUMMARY},
      kind="write", confirm=True)
def log_lesson(m: CurrentMember, db: Session, class_subject_id: uuid.UUID,
               note: str | None = None, topic_id: uuid.UUID | None = None,
               coverage: str = "full", period_no: int | None = None,
               on_date: date | None = None):
    body = LessonLogIn(class_subject_id=class_subject_id, topic_id=topic_id,
                       coverage=coverage, date=on_date, note=note,
                       period_no=period_no)
    return ClassroomService(db).log(m, body)


@tool("assign_homework",
      "Assign homework for a class-subject — whole class, or one student via "
      "student_id. Guardians are notified automatically when it's assigned.",
      params={"class_subject_id": {**_UUID, "required": True},
              "text": {"type": "string", "required": True},
              "due_date": _DATE,
              "student_id": {**_UUID, "description": "one student only; omit for whole class"},
              "summary": _SUMMARY},
      kind="write", confirm=True)
def assign_homework(m: CurrentMember, db: Session, class_subject_id: uuid.UUID,
                    text: str, due_date: date | None = None,
                    student_id: uuid.UUID | None = None):
    body = HomeworkIn(class_subject_id=class_subject_id, text=text,
                      due_date=due_date, student_id=student_id)
    return ClassroomService(db).add_homework(m, body)


@tool("add_plan_comment",
      "Leave a change-request comment on a class-subject's syllabus plan "
      "(e.g. a teacher asking the admin to resize a chapter).",
      params={"class_subject_id": {**_UUID, "required": True},
              "text": {"type": "string", "required": True},
              "topic_id": {**_UUID, "description": "anchor to one topic"},
              "summary": _SUMMARY},
      kind="write", confirm=True)
def add_plan_comment(m: CurrentMember, db: Session, class_subject_id: uuid.UUID,
                     text: str, topic_id: uuid.UUID | None = None):
    return PlannerService(db).add_comment(
        m, class_subject_id, PlanCommentIn(text=text, topic_id=topic_id))


@tool("confirm_check",
      "Confirm a daily check as done by the class ('class did it'), flagging "
      "only the exception students. Empty exceptions = the whole class did it.",
      params={"check_id": {**_UUID, "required": True},
              "exceptions": {
                  "type": "array",
                  "description": "deviating students only",
                  "items": {"type": "object", "properties": {
                      "student_id": {"type": "string", "format": "uuid"},
                      "status": {"type": "string", "enum": ["not_done", "note"]},
                      "note": {"type": "string"}},
                      "required": ["student_id", "status"]}},
              "summary": _SUMMARY},
      kind="write", confirm=True)
def confirm_check(m: CurrentMember, db: Session, check_id: uuid.UUID,
                  exceptions: list | None = None):
    return RecommendationsService(db).confirm(
        m, check_id, CheckConfirmIn(exceptions=exceptions or []))
