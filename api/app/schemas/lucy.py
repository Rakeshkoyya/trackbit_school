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
    # A clarifying question this assistant turn ended on (GA §4).
    question: dict[str, Any] | None = None
    # The composed view this turn saved, if any (GA §5).
    view_id: str | None = None


class LucyViewSummary(BaseModel):
    id: uuid.UUID
    title: str
    summary: str | None = None
    widget_count: int
    created_at: datetime


class LucyViewOut(BaseModel):
    id: uuid.UUID
    title: str
    summary: str | None = None
    signature: str = ""
    # [{heading, narrative?, widget_ids: [...]}]
    sections: list[dict[str, Any]] = Field(default_factory=list)
    # Self-contained widget envelopes (data + config + source bindings).
    widgets: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime
    refreshed_at: datetime | None = None


class ConversationOut(BaseModel):
    id: uuid.UUID
    title: str | None
    created_at: datetime
    updated_at: datetime


class ConversationDetail(ConversationOut):
    messages: list[MessageOut] = Field(default_factory=list)
