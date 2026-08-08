"""Agent connectors — issue, list and revoke credentials; and the token's own
identity endpoint (`D-97`, MCP-SERVER-PLAN §4 and §6).

Two routers, because they authenticate differently and that difference is the
point:

- `router` (`/org/api-tokens`) is driven by a **human** with a JWT, from the
  Connections screen. Issuing a credential is a human act.
- `agent_router` (`/agent`) is driven by the **connector**, with the opaque
  token it was given. A JWT is not accepted there, and a connector token is not
  accepted anywhere else.

`GET /agent/me` is deliberately the first thing to exist on the agent side: it
is the "test connection" round trip for the screen, and the honest answer to
"what am I and what may I do" before any transport exists.
"""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.database import get_db
from app.core.dependencies import (
    AgentPrincipal,
    get_agent_principal,
    get_current_member,
)
from app.schemas.api_token import (
    AgentIdentity,
    ApiTokenCreate,
    ApiTokenCreated,
    ApiTokenOut,
)
from app.services.api_tokens import ApiTokenService
from app.services.lucy.registry import visible_tools

router = APIRouter()
agent_router = APIRouter()


@router.post("/api-tokens", response_model=ApiTokenCreated,
             status_code=status.HTTP_201_CREATED)
def create_api_token(
    body: ApiTokenCreate,
    member: CurrentMember = Depends(get_current_member),
    db: Session = Depends(get_db),
) -> ApiTokenCreated:
    """Issue a connector credential with **this member's** authority.

    Not `require_admin`: `D-103` lets a school open this to teachers, and the
    service decides from `org.agent_access`. The authority ceiling is the
    issuer's own either way — a teacher's connector can never exceed her.
    """
    row, secret = ApiTokenService(db).issue(
        member, name=body.name, scopes=body.scopes, mode=body.mode,
        expires_days=body.expires_days)
    return ApiTokenCreated(token=ApiTokenOut.model_validate(row), secret=secret)


@router.get("/api-tokens", response_model=list[ApiTokenOut])
def list_api_tokens(
    member: CurrentMember = Depends(get_current_member),
    db: Session = Depends(get_db),
) -> list[ApiTokenOut]:
    """An admin sees the school's connectors; a teacher sees her own."""
    return [ApiTokenOut.model_validate(r)
            for r in ApiTokenService(db).list_for(member)]


@router.delete("/api-tokens/{token_id}", response_model=ApiTokenOut)
def revoke_api_token(
    token_id: uuid.UUID,
    member: CurrentMember = Depends(get_current_member),
    db: Session = Depends(get_db),
) -> ApiTokenOut:
    """Revoke, never delete: the row stays so the Activity trail keeps naming
    the connector behind each call."""
    return ApiTokenOut.model_validate(ApiTokenService(db).revoke(member, token_id))


@agent_router.get("/me", response_model=AgentIdentity)
def agent_me(
    principal: AgentPrincipal = Depends(get_agent_principal),
) -> AgentIdentity:
    """Who this connector acts as, and what it actually reaches.

    `tools` and `domains` are computed through `visible_tools` with the
    credential's own scope, so this reports the **real** surface rather than
    what was asked for when the token was issued — if a role changed, the
    difference shows up here first.
    """
    m = principal.member
    specs = visible_tools(m, scope=set(principal.scopes), transport="mcp")
    return AgentIdentity(
        org_id=m.org_id,
        org_name=m.org.name,
        member_name=m.user.name,
        org_role=m.org_role,
        mode=principal.mode,
        scopes=sorted(principal.scopes),
        tools=len(specs),
        domains=sorted({s.domain for s in specs}),
    )
