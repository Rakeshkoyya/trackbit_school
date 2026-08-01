"""Task schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class AssigneeOut(BaseModel):
    id: uuid.UUID
    name: str


class TaskSubjectOut(BaseModel):
    """What the task is about (D-46): a student, a member, or — since V1-6's
    `D-16` — a class-subject, resolved to a name so the row reads "Kabir Shah —
    absent 4 days" or "6-B Maths" instead of a bare title."""

    type: str  # student | member | class_subject
    id: uuid.UUID
    name: str


class TaskOut(BaseModel):
    id: uuid.UUID
    board_id: uuid.UUID
    board_name: str
    title: str
    description: str | None = None
    category: str | None = None
    priority: int = 0
    assignee: AssigneeOut | None = None
    due_at: datetime | None = None
    all_day: bool = False
    status: str
    pass_count: int = 0
    is_critical: bool = False
    passed_by: str | None = None  # name of who last passed it (home transparency)
    subject: TaskSubjectOut | None = None  # D-46
    outcome: str | None = None  # D-46: "what happened?" once completed
    # S-106: who asked for this (latest 'assigned' actor ≠ assignee) and when.
    asked_by: str | None = None
    asked_at: datetime | None = None
    created_at: datetime


class TaskEventOut(BaseModel):
    id: int
    type: str
    actor_name: str | None = None
    at: datetime
    text: str  # human-rendered ("Passed to Priya")


class TaskDetailOut(TaskOut):
    events: list[TaskEventOut] = []
    assignable: list[AssigneeOut] = []  # pool for the reassign picker
    can_cancel: bool = False


class TaskCreateRequest(BaseModel):
    board_id: uuid.UUID
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    category: str | None = Field(default=None, max_length=60)
    priority: int = Field(default=0, ge=0, le=3)
    assignee_id: uuid.UUID | None = None  # None = leave unassigned (claimable)
    due_at: datetime | None = None
    all_day: bool = False
    is_critical: bool = False
    # D-46: what the task is about. Set by the action rail; validated org-scoped.
    # V1-6 adds `class_subject` for `D-16`'s catch-up request, which is a task
    # about a subject in a class rather than about a person — and which is what
    # lets the syllabus board read back whether the meeting has happened yet.
    subject_type: str | None = Field(
        default=None, pattern="^(student|member|class_subject)$")
    subject_id: uuid.UUID | None = None


class TaskUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    category: str | None = Field(default=None, max_length=60)
    due_at: datetime | None = None
    all_day: bool | None = None
    is_critical: bool | None = None
    priority: int | None = Field(default=None, ge=0, le=3)
    board_id: uuid.UUID | None = None  # set to move the task to another board


class AssignRequest(BaseModel):
    user_id: uuid.UUID | None = None  # None = unassign


class MakeRecurringRequest(BaseModel):
    days: list[str] = Field(min_length=1)  # weekday codes: mon..sun
    time: str | None = None  # "HH:MM"; None = all-day


class ReassignRequest(BaseModel):
    to_user_id: uuid.UUID


class CompleteRequest(BaseModel):
    """D-46: completion asks one OPTIONAL question — what happened?
    "Spoke to the father — fever, back Monday" is the fact the admin wanted
    when they pressed the button. Empty body keeps the one-tap complete."""

    outcome: str | None = Field(default=None, max_length=500)


class CompleteResponse(BaseModel):
    status: str
    already_done: bool = False
    completed_by_name: str | None = None


# ---- attachments (S2, P4-BE-02) ---------------------------------------
class NoteCreateRequest(BaseModel):
    content: str = Field(min_length=1, max_length=2000)


class AttachmentOut(BaseModel):
    id: uuid.UUID
    kind: str  # note | photo
    content: str | None = None  # note text
    file_url: str | None = None  # photo URL
    uploaded_by_name: str
    created_at: datetime
