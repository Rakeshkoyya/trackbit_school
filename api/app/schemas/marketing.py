"""Marketing schemas — the public demo request and its super-admin read view."""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, model_validator

from app.models.marketing import DEMO_REQUEST_STATUSES


class DemoRequestCreate(BaseModel):
    """Posted by the public landing page. No auth, no org — see models/marketing.py."""

    school_name: str = Field(min_length=1, max_length=160)
    contact_name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    phone: str = Field(min_length=6, max_length=32)
    city: str | None = Field(default=None, max_length=120)
    student_count: int | None = Field(default=None, ge=0, le=100_000)
    message: str | None = Field(default=None, max_length=2000)
    source: str = Field(default="landing", max_length=60)


class DemoRequestAck(BaseModel):
    """What the public gets back: proof it landed, nothing else."""

    id: uuid.UUID
    received: bool = True


class DemoRequestOut(BaseModel):
    id: uuid.UUID
    school_name: str
    contact_name: str
    email: str
    phone: str
    city: str | None
    student_count: int | None
    message: str | None
    source: str
    status: str
    created_at: datetime
    # Working state, so the operator can see at a glance which leads have been
    # touched without opening each one.
    note_count: int = 0
    last_activity_at: datetime | None = None


class DemoRequestNoteOut(BaseModel):
    """One append-only history entry. `note` alone = a remark; `status_to` set =
    a status move (with `status_from` for what it moved off)."""

    id: uuid.UUID
    created_at: datetime
    author_name: str | None
    note: str | None
    status_from: str | None
    status_to: str | None


class DemoRequestDetail(DemoRequestOut):
    notes: list[DemoRequestNoteOut] = []


class DemoRequestUpdate(BaseModel):
    """One operator action: a remark, a status move, or both in a single row."""

    status: str | None = None
    note: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def _something_to_record(self) -> "DemoRequestUpdate":
        if self.status is None and not (self.note or "").strip():
            raise ValueError("Write a remark or pick a status.")
        if self.status is not None and self.status not in DEMO_REQUEST_STATUSES:
            raise ValueError(f"Status must be one of: {', '.join(DEMO_REQUEST_STATUSES)}.")
        return self
