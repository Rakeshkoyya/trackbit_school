"""AgentContext — a frozen, connection-free snapshot of who is asking.

Captured BEFORE streaming starts, because the agent loop must never hold a DB
session (or an ORM object bound to one) across a 45-second model call — the
Aiven server allows 20 connections in total. Everything the loop needs about
the member is plain data here."""

import uuid
from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class AgentContext:
    org_id: uuid.UUID
    org_name: str
    membership_id: uuid.UUID
    user_id: uuid.UUID
    member_name: str
    role: str  # "admin" | "teacher"
    today: str  # ISO date
    weekday: str
    year_id: uuid.UUID | None = None
    year_label: str | None = None
    # Teacher's taught classes: [{id, label, subjects: [names]}]
    classes: list[dict] = field(default_factory=list)

    @classmethod
    def today_parts(cls) -> tuple[str, str]:
        t = date.today()
        return t.isoformat(), t.strftime("%A")
