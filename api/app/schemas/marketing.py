"""Marketing schemas — the public demo request and its super-admin read view."""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


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
