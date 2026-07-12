"""Lucy chat schemas."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class LucyMeta(BaseModel):
    ai_configured: bool
    suggested_prompts: list[str]


class ConversationCreate(BaseModel):
    title: str | None = Field(default=None, max_length=120)


class MessageIn(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class WidgetOut(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    message_id: uuid.UUID
    type: str
    title: str
    spec_version: int
    data: Any
    config: dict[str, Any] = Field(default_factory=dict)
    source_tool: str | None = None
    pinned: bool = False
    pinned_at: datetime | None = None
    refreshed_at: datetime | None = None
    created_at: datetime


class PendingActionOut(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    message_id: uuid.UUID | None = None
    tool: str
    summary: str
    params: dict[str, Any] = Field(default_factory=dict)
    status: str
    result: dict[str, Any] | None = None
    error: str | None = None
    expires_at: datetime
    created_at: datetime


class MessageOut(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    created_at: datetime
    widgets: list[WidgetOut] = Field(default_factory=list)
    actions: list[PendingActionOut] = Field(default_factory=list)


class ConversationOut(BaseModel):
    id: uuid.UUID
    title: str | None
    created_at: datetime
    updated_at: datetime


class ConversationDetail(ConversationOut):
    messages: list[MessageOut] = Field(default_factory=list)
