"""Streamable HTTP transport + OAuth discovery for the MCP server.

Two routers, both mounted at the **application root** (not under `/api/v1`):

- `well_known_router` — RFC 9728 protected-resource metadata and RFC 8414
  authorization-server metadata. These must live at `/.well-known/...` on the
  origin, which is why they cannot sit under the versioned API prefix.
- `mcp_router` — the single MCP endpoint at `/mcp`, POST + GET + DELETE.

The discovery handshake is the part that is easy to get subtly wrong, so it is
worth stating plainly: an unauthenticated request to `/mcp` must return **401**
with `WWW-Authenticate: Bearer resource_metadata="..."`. Claude does not honour
that header on a 200, and without it the client never learns where the
authorization server is — the symptom is "Couldn't reach the MCP server" while
this server's own logs show the request arriving fine.
"""

import json
import logging
from typing import Any
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import _engage_rls
from app.core.exceptions import AppError
from app.services.api_tokens import ApiTokenService
from app.services.lucy import domains, manual
from app.services.lucy.registry import execute, visible_tools

logger = logging.getLogger(__name__)

well_known_router = APIRouter()
mcp_router = APIRouter()

# The newest spec revision this server implements. Claude negotiates down, and
# a client that asks for something older still gets a working session.
PROTOCOL_VERSION = "2025-11-25"
SUPPORTED_PROTOCOLS = ("2025-11-25", "2025-06-18", "2025-03-26")

SERVER_INFO = {"name": "trackbit-school", "title": "TrackBit School",
               "version": "1.0.0"}

MCP_PATH = "/mcp"

# JSON-RPC error codes (the spec's, not ours).
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


def public_base_url(request: Request) -> str:
    """The externally-visible origin of this server.

    Derived from the request rather than configured, because the value has to
    match what the user typed into Claude — and that is `https://api.trackbit.in`
    in production and `http://localhost:8000` on the founder's laptop. A
    hardcoded setting would be wrong in one of them. Honours the proxy headers
    Traefik sets, since the app itself is reached over plain HTTP behind it.
    """
    forwarded_proto = request.headers.get("x-forwarded-proto")
    forwarded_host = request.headers.get("x-forwarded-host")
    scheme = (forwarded_proto or request.url.scheme).split(",")[0].strip()
    host = (forwarded_host or request.headers.get("host")
            or request.url.netloc).split(",")[0].strip()
    return f"{scheme}://{host}"


def resource_url(request: Request) -> str:
    return public_base_url(request) + MCP_PATH


def _unauthorized(request: Request, description: str = "") -> JSONResponse:
    """The 401 that starts the whole OAuth dance."""
    base = public_base_url(request)
    challenge = (
        f'Bearer resource_metadata="{base}/.well-known/oauth-protected-resource"'
    )
    if description:
        challenge += f', error="invalid_token", error_description="{description}"'
    return JSONResponse(
        status_code=401,
        content={"jsonrpc": "2.0", "id": None,
                 "error": {"code": INVALID_REQUEST,
                           "message": description or "Authentication required."}},
        headers={"WWW-Authenticate": challenge},
    )


# ---------------------------------------------------------------------------
# Discovery


def _prm(request: Request) -> dict:
    base = public_base_url(request)
    return {
        # MUST equal the URL the user entered in Claude, path included.
        "resource": resource_url(request),
        # Claude uses the FIRST entry and does not fall back — so list one.
        "authorization_servers": [base],
        "scopes_supported": sorted(domains.DOMAIN_NAMES),
        "bearer_methods_supported": ["header"],
        "resource_documentation": f"{base}/docs",
    }


@well_known_router.get("/.well-known/oauth-protected-resource")
def protected_resource_metadata(request: Request) -> dict:
    return _prm(request)


@well_known_router.get("/.well-known/oauth-protected-resource/mcp")
def protected_resource_metadata_pathed(request: Request) -> dict:
    """Claude probes the path-suffixed form first when the 401 carried no
    pointer. Serving both costs nothing and removes a failure mode."""
    return _prm(request)


@well_known_router.get("/.well-known/oauth-authorization-server")
@well_known_router.get("/.well-known/oauth-authorization-server/mcp")
def authorization_server_metadata(request: Request) -> dict:
    base = public_base_url(request)
    return {
        "issuer": base,
        "authorization_endpoint": f"{base}/oauth/authorize",
        "token_endpoint": f"{base}/oauth/token",
        "revocation_endpoint": f"{base}/oauth/revoke",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        # Required so a spec-compliant client can verify PKCE support before it
        # starts the flow.
        "code_challenge_methods_supported": ["S256"],
        # `none` covers public clients (PKCE only); the two `client_secret_*`
        # methods cover a connector that was given a secret.
        "token_endpoint_auth_methods_supported": [
            "none", "client_secret_post", "client_secret_basic"],
        "scopes_supported": sorted(domains.DOMAIN_NAMES) + ["offline_access"],
        "service_documentation": f"{base}/docs",
    }


# ---------------------------------------------------------------------------
# Auth for the MCP endpoint


class McpPrincipal:
    """Resolved connector identity for one MCP request."""

    def __init__(self, member, token):
        self.member = member
        self.token = token
        # Intersected with the live toolsets on purpose: a credential issued
        # before a toolset was retired still carries its name, and an unknown
        # name reaches `resolve_scope` as a ValueError — a 500 on every call
        # rather than "that toolset is simply not granted".
        self.scopes = frozenset(token.scopes or []) & domains.DOMAIN_NAMES
        self.can_write = token.mode == "read_write"


def _authenticate(request: Request, db: Session) -> "McpPrincipal | JSONResponse":
    auth = request.headers.get("authorization") or ""
    if not auth.lower().startswith("bearer "):
        return _unauthorized(request)
    raw = auth.split(" ", 1)[1].strip()
    ip = request.client.host if request.client else None
    try:
        member, token = ApiTokenService(db).resolve(raw, ip=ip)
    except AppError:
        return _unauthorized(request, "The access token is invalid or expired.")

    # RFC 8707 audience binding: a token minted for another resource must not
    # work here, even though it is a perfectly valid token of ours.
    if token.audience:
        want = urlsplit(resource_url(request))
        got = urlsplit(token.audience)
        if (want.hostname, want.path.rstrip("/")) != (got.hostname,
                                                      got.path.rstrip("/")):
            return _unauthorized(request,
                                 "This token was issued for a different resource.")

    _engage_rls(db, member.org_id)
    return McpPrincipal(member, token)


# ---------------------------------------------------------------------------
# JSON-RPC


def _result(req_id: Any, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _error(req_id: Any, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": req_id,
            "error": {"code": code, "message": message}}


def _tool_schema(spec) -> dict:
    """A registry ToolSpec as an MCP tool object.

    `inputSchema` is camelCase — the one place in this codebase where that is
    correct, because it is the MCP wire format rather than our own.
    """
    return {
        "name": spec.name,
        "description": " ".join(spec.description.split()),
        "inputSchema": spec.params_schema,
        # Advisory, but a client can only surface "this tool writes" to the
        # user if we say so.
        "annotations": {
            "readOnlyHint": spec.kind == "read",
            "destructiveHint": False,
            "idempotentHint": spec.kind == "read",
            "openWorldHint": False,
        },
    }


def _visible(principal: McpPrincipal):
    return visible_tools(principal.member, scope=set(principal.scopes),
                         transport="mcp")


def _handle(message: dict, principal: McpPrincipal, db: Session,
            request: Request) -> dict | None:
    """Dispatch one JSON-RPC message. Returns None for notifications."""
    method = message.get("method")
    req_id = message.get("id")
    params = message.get("params") or {}
    is_notification = "id" not in message

    if method == "initialize":
        asked = (params.get("protocolVersion") or "").strip()
        version = asked if asked in SUPPORTED_PROTOCOLS else PROTOCOL_VERSION
        return _result(req_id, {
            "protocolVersion": version,
            "capabilities": {
                "tools": {"listChanged": False},
                "resources": {"subscribe": False, "listChanged": False},
            },
            "serverInfo": SERVER_INFO,
            "instructions": (
                "TrackBit School — the school's operating system. Call "
                "get_school_structure before anything that needs an id; never "
                "invent one. Read school://manual for the vocabulary and for "
                "how figures must be reported."
            ),
        })

    if is_notification:
        # notifications/initialized, notifications/cancelled, ... — nothing to
        # answer. The transport layer turns this into a 202.
        return None

    if method == "ping":
        return _result(req_id, {})

    if method == "tools/list":
        return _result(req_id, {
            "tools": [_tool_schema(s) for s in _visible(principal)]})

    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        spec = next((s for s in _visible(principal) if s.name == name), None)
        if spec is None:
            # Out of scope and non-existent give the same answer on purpose: a
            # distinguishable error is a directory of what exists elsewhere.
            return _error(req_id, INVALID_PARAMS, f"Unknown tool: {name}")
        if spec.kind == "write" and not principal.can_write:
            # A tool-execution error, not a protocol error — the model can read
            # this and stop trying.
            return _result(req_id, {
                "content": [{"type": "text",
                             "text": "This connection is read-only, so "
                                     f"{name} cannot be called."}],
                "isError": True})

        execution = execute(spec, principal.member, db, args,
                            scope=set(principal.scopes))
        if not execution.ok:
            return _result(req_id, {
                "content": [{"type": "text",
                             "text": f"{execution.error_code}: "
                                     f"{execution.error_message}"}],
                "isError": True})
        data = execution.result.data
        return _result(req_id, {
            "content": [{"type": "text",
                         "text": json.dumps(data, separators=(",", ":"),
                                            default=str)}],
            "structuredContent": data if isinstance(data, dict) else {"data": data},
            "isError": False})

    if method == "resources/list":
        return _result(req_id, {"resources": [{
            "uri": "school://manual",
            "name": "manual",
            "title": "TrackBit School agent manual",
            "description": "How this school's data is shaped, how to resolve "
                           "ids, and how figures must be reported.",
            "mimeType": "text/markdown",
        }]})

    if method == "resources/read":
        uri = params.get("uri")
        if uri != "school://manual":
            return _error(req_id, INVALID_PARAMS, f"Unknown resource: {uri}")
        text = manual.build_manual(principal.member, scope=set(principal.scopes))
        return _result(req_id, {"contents": [{
            "uri": uri, "mimeType": "text/markdown", "text": text}]})

    if method == "prompts/list":
        return _result(req_id, {"prompts": []})

    return _error(req_id, METHOD_NOT_FOUND, f"Unknown method: {method}")


# ---------------------------------------------------------------------------
# Transport


def _origin_ok(request: Request) -> bool:
    """DNS-rebinding guard required by the transport spec. Browsers send
    Origin; Claude's server-side fetch does not, and an absent Origin is not a
    rebinding attack — only a *present, foreign* one is."""
    origin = request.headers.get("origin")
    if not origin:
        return True
    host = urlsplit(origin).hostname or ""
    allowed = {urlsplit(o).hostname for o in (settings.CORS_ORIGINS or [])}
    allowed.discard(None)
    return host in allowed or host in ("localhost", "127.0.0.1")


@mcp_router.post(MCP_PATH)
async def mcp_post(request: Request, db: Session = Depends(get_db)):
    if not _origin_ok(request):
        return JSONResponse(status_code=403, content={
            "jsonrpc": "2.0", "id": None,
            "error": {"code": INVALID_REQUEST, "message": "Origin not allowed."}})

    version = request.headers.get("mcp-protocol-version")
    if version and version not in SUPPORTED_PROTOCOLS:
        return JSONResponse(status_code=400, content={
            "jsonrpc": "2.0", "id": None,
            "error": {"code": INVALID_REQUEST,
                      "message": f"Unsupported MCP-Protocol-Version: {version}"}})

    principal = _authenticate(request, db)
    if isinstance(principal, JSONResponse):
        return principal

    try:
        body = json.loads(await request.body())
    except ValueError:
        return JSONResponse(status_code=400, content=_error(
            None, PARSE_ERROR, "Request body is not valid JSON."))

    batch = isinstance(body, list)
    messages = body if batch else [body]
    replies: list[dict] = []
    for message in messages:
        if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
            replies.append(_error(None, INVALID_REQUEST,
                                  "Not a JSON-RPC 2.0 message."))
            continue
        try:
            reply = _handle(message, principal, db, request)
        except AppError as exc:
            reply = _error(message.get("id"), INTERNAL_ERROR, exc.message)
        except Exception:
            logger.exception("mcp method %s crashed", message.get("method"))
            reply = _error(message.get("id"), INTERNAL_ERROR,
                           "The server hit an internal error.")
        if reply is not None:
            replies.append(reply)

    if not replies:
        # Everything in the batch was a notification or a response.
        return Response(status_code=202)
    return JSONResponse(content=replies if batch else replies[0])


@mcp_router.get(MCP_PATH)
async def mcp_get(request: Request, db: Session = Depends(get_db)):
    """The optional server-initiated SSE stream.

    We have nothing to push — no subscriptions, no sampling, no list-changed
    notifications — so the honest answer is 405, which the spec names
    explicitly for exactly this case. Authenticating first keeps the 401
    discovery handshake reachable on GET too, which is how some clients probe.
    """
    principal = _authenticate(request, db)
    if isinstance(principal, JSONResponse):
        return principal
    return Response(status_code=405, headers={"Allow": "POST, DELETE"})


@mcp_router.delete(MCP_PATH)
async def mcp_delete(request: Request, db: Session = Depends(get_db)):
    """Session teardown. This server is stateless between calls — every request
    carries its own bearer token and nothing is held server-side — so there is
    no session to end. 204 rather than 405 because the client's intent (stop)
    is satisfied."""
    principal = _authenticate(request, db)
    if isinstance(principal, JSONResponse):
        return principal
    return Response(status_code=204)
