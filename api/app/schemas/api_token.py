"""Schemas for agent connector credentials (`D-97`).

`ApiTokenOut` carries **no secret** — not the raw token, not its hash. The raw
value exists in exactly one response, `ApiTokenCreated`, and then never again;
that is what makes "you will not see this again" on the issue screen true rather
than a UI convention.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ApiTokenCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    # Toolset names from services/lucy/domains.py. `core` is folded in server
    # side; a scope the issuer cannot reach is refused, not silently dropped.
    scopes: list[str] = Field(min_length=1)
    mode: str = Field(default="read", pattern="^(read|read_write)$")
    expires_days: int | None = None


class ApiTokenOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    prefix: str  # first 12 chars, so two connectors are tellable apart
    scopes: list[str]
    mode: str
    created_at: datetime
    expires_at: datetime | None = None
    last_used_at: datetime | None = None
    last_used_ip: str | None = None
    revoked_at: datetime | None = None


class ApiTokenCreated(BaseModel):
    """The only response that ever contains the raw token."""

    token: ApiTokenOut
    # Shown once, with an explicit "you will not see this again". It is stored
    # nowhere and cannot be recovered — only re-issued.
    secret: str


class OAuthClientCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    scopes: list[str] = Field(min_length=1)
    mode: str = Field(default="read", pattern="^(read|read_write)$")
    # Claude's connector UI makes the secret optional, so a public (PKCE-only)
    # client is a legitimate shape — but the default is the safer one.
    confidential: bool = True
    # Defaults cover Claude's hosted callback plus Claude Code's loopback.
    redirect_uris: list[str] | None = None


class OAuthClientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    client_id: str
    scopes: list[str]
    mode: str
    redirect_uris: list[str]
    # Whether a secret exists — never the secret itself.
    confidential: bool = False
    created_at: datetime
    last_used_at: datetime | None = None
    revoked_at: datetime | None = None

    @classmethod
    def model_validate(cls, obj, **kw):  # type: ignore[override]
        out = super().model_validate(obj, **kw)
        out.confidential = getattr(obj, "client_secret_hash", None) is not None
        return out


class OAuthClientCreated(BaseModel):
    """The only response that ever contains the client secret."""

    client: OAuthClientOut
    client_secret: str | None = None


class OAuthConsentSummary(BaseModel):
    """What the consent screen renders — the real reachable surface."""

    client_name: str
    org_name: str
    member_name: str
    mode: str
    scopes: list[str]
    tool_count: int
    domains: list[str]
    writes: list[str]


class OAuthConsentIn(BaseModel):
    client_id: str
    redirect_uri: str
    code_challenge: str
    code_challenge_method: str = Field(default="S256", pattern="^S256$")
    scope: str | None = None
    state: str | None = None
    resource: str | None = None
    issuer: str | None = None


class OAuthConsentOut(BaseModel):
    redirect_to: str


class AgentIdentity(BaseModel):
    """What `GET /agent/me` answers: who this connector acts as, and what it may
    do. The "test connection" round trip, and the model's first orientation."""

    org_id: uuid.UUID
    org_name: str
    member_name: str
    org_role: str
    mode: str
    scopes: list[str]
    tools: int  # how many tools this credential actually resolves to
    domains: list[str]
