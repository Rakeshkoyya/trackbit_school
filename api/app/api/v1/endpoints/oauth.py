"""OAuth endpoints — the authorization server's public face (`D-99`).

Two routers, and the split matters:

- `root_router` is mounted at the application root, because the issuer that
  `/.well-known/oauth-authorization-server` advertises is the bare origin. If
  `/oauth/token` lived under `/api/v1`, the metadata would have to lie about it.
- `router` is the ordinary `/api/v1/org/...` surface the Connections screen
  drives with a normal staff JWT.

The authorize endpoint does **not** render consent itself. It validates the
request, then bounces the browser to the web app, which already knows how to log
a staff member in. The web app posts back to `/api/v1/org/oauth-consent` with
that member's own session, and the code is minted there — so consent is always
tied to a real, logged-in member of this school.
"""

import base64
import uuid
from datetime import UTC, datetime
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.context import CurrentMember
from app.core.database import get_db
from app.core.dependencies import get_current_member
from app.core.security import hash_token
from app.models import ApiToken
from app.schemas.api_token import (
    OAuthClientCreate,
    OAuthClientCreated,
    OAuthClientOut,
    OAuthConsentIn,
    OAuthConsentOut,
    OAuthConsentSummary,
)
from app.services.oauth import OAuthError, OAuthService

router = APIRouter()
root_router = APIRouter()


def _oauth_error_response(exc: OAuthError) -> JSONResponse:
    """RFC 6749 error shape — deliberately *not* this codebase's usual
    `{error: {code, message}}` envelope. OAuth clients parse the flat form, and
    Claude keys its refresh behaviour on `error == "invalid_grant"`."""
    headers = ({"WWW-Authenticate": 'Basic realm="oauth"'}
               if exc.status_code == 401 else None)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.oauth_error, "error_description": exc.message},
        headers=headers,
    )


# ---------------------------------------------------------------------------
# The authorization endpoint (root)


@root_router.get("/oauth/authorize")
def authorize(
    request: Request,
    client_id: str = "",
    redirect_uri: str = "",
    response_type: str = "code",
    code_challenge: str = "",
    code_challenge_method: str = "",
    scope: str | None = None,
    state: str | None = None,
    resource: str | None = None,
    db: Session = Depends(get_db),
):
    """Validate, then hand off to the web app's consent screen.

    Errors here render as JSON rather than redirecting: until `redirect_uri` has
    been checked against the client's allowlist it is attacker-controlled, and
    bouncing to it would make this an open redirect (OAuth 2.1 4.1.2.1).
    """
    svc = OAuthService(db)
    try:
        svc.begin_authorization(
            client_id=client_id, redirect_uri=redirect_uri,
            response_type=response_type, code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
            scope=scope, resource=resource)
    except OAuthError as exc:
        return _oauth_error_response(exc)

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "code_challenge": code_challenge,
        "code_challenge_method": code_challenge_method,
    }
    for key, value in (("scope", scope), ("state", state),
                       ("resource", resource)):
        if value:
            params[key] = value
    target = f"{settings.FRONTEND_BASE_URL}/oauth/consent?{urlencode(params)}"
    return RedirectResponse(target, status_code=302)


# ---------------------------------------------------------------------------
# The token endpoint (root)


@root_router.post("/oauth/token")
def token(
    request: Request,
    grant_type: str = Form(...),
    code: str | None = Form(None),
    code_verifier: str | None = Form(None),
    redirect_uri: str | None = Form(None),
    refresh_token: str | None = Form(None),
    client_id: str | None = Form(None),
    client_secret: str | None = Form(None),
    scope: str | None = Form(None),
    resource: str | None = Form(None),
    db: Session = Depends(get_db),
):
    """Token exchange and refresh.

    `Form(...)` rather than a Pydantic body on purpose: RFC 6749 requires
    `application/x-www-form-urlencoded`, and Claude sends both the initial
    exchange and every refresh that way. A JSON-only parser here answers 415 and
    the connector fails with no useful message.

    A client may authenticate with HTTP Basic instead of form fields
    (`client_secret_basic`), so both are read.
    """
    svc = OAuthService(db)

    if not client_id or not client_secret:
        header = request.headers.get("authorization") or ""
        if header.lower().startswith("basic "):
            try:
                decoded = base64.b64decode(header.split(" ", 1)[1]).decode()
                basic_id, _, basic_secret = decoded.partition(":")
                client_id = client_id or basic_id or None
                client_secret = client_secret or basic_secret or None
            except (ValueError, UnicodeDecodeError):
                pass

    try:
        if grant_type == "authorization_code":
            if not (code and code_verifier and redirect_uri and client_id):
                raise OAuthError(
                    "invalid_request",
                    "code, code_verifier, redirect_uri and client_id are required.")
            body = svc.exchange_code(
                code=code, client_id=client_id, client_secret=client_secret,
                code_verifier=code_verifier, redirect_uri=redirect_uri,
                resource=resource)
        elif grant_type == "refresh_token":
            if not (refresh_token and client_id):
                raise OAuthError("invalid_request",
                                 "refresh_token and client_id are required.")
            body = svc.refresh(refresh_token=refresh_token, client_id=client_id,
                               client_secret=client_secret, scope=scope)
        else:
            raise OAuthError("unsupported_grant_type",
                             f"Unsupported grant_type: {grant_type}")
    except OAuthError as exc:
        db.rollback()
        return _oauth_error_response(exc)

    db.commit()
    # Tokens must never be cached by an intermediary.
    return JSONResponse(content=body, headers={"Cache-Control": "no-store",
                                               "Pragma": "no-cache"})


@root_router.post("/oauth/revoke")
def revoke_token(
    token: str = Form(...),
    client_id: str | None = Form(None),
    client_secret: str | None = Form(None),
    db: Session = Depends(get_db),
) -> Response:
    """RFC 7009. Always 200 — telling a caller whether an unknown token existed
    is itself an oracle."""
    digest = hash_token(token)
    row = db.scalar(select(ApiToken).where(or_(
        ApiToken.token_hash == digest, ApiToken.refresh_token_hash == digest)))
    if row is not None and row.revoked_at is None:
        row.revoked_at = datetime.now(UTC)
        db.commit()
    return Response(status_code=200)


# ---------------------------------------------------------------------------
# Client management + consent (under /api/v1/org)


@router.post("/oauth-clients", response_model=OAuthClientCreated, status_code=201)
def create_oauth_client(
    body: OAuthClientCreate,
    member: CurrentMember = Depends(get_current_member),
    db: Session = Depends(get_db),
) -> OAuthClientCreated:
    """Generate a connector's Client ID and Secret. The secret is returned once
    and is not recoverable — only re-issuable."""
    row, secret = OAuthService(db).create_client(
        member, name=body.name, scopes=body.scopes, mode=body.mode,
        redirect_uris=body.redirect_uris, confidential=body.confidential)
    return OAuthClientCreated(client=OAuthClientOut.model_validate(row),
                              client_secret=secret)


@router.get("/oauth-clients", response_model=list[OAuthClientOut])
def list_oauth_clients(
    member: CurrentMember = Depends(get_current_member),
    db: Session = Depends(get_db),
) -> list[OAuthClientOut]:
    return [OAuthClientOut.model_validate(r)
            for r in OAuthService(db).list_clients(member)]


@router.delete("/oauth-clients/{client_pk}", response_model=OAuthClientOut)
def revoke_oauth_client(
    client_pk: uuid.UUID,
    member: CurrentMember = Depends(get_current_member),
    db: Session = Depends(get_db),
) -> OAuthClientOut:
    """Revoke the connector **and every token it issued** — the point of the
    button is that Claude loses access now, not at the next login."""
    return OAuthClientOut.model_validate(
        OAuthService(db).revoke_client(member, client_pk))


@router.get("/oauth-consent", response_model=OAuthConsentSummary)
def consent_summary(
    client_id: str,
    scope: str | None = None,
    member: CurrentMember = Depends(get_current_member),
    db: Session = Depends(get_db),
) -> OAuthConsentSummary:
    """What the consent screen renders: the real tool surface this connection
    would reach, computed through `visible_tools` with the member's own
    authority — not the client's wish list."""
    svc = OAuthService(db)
    client = svc.load_client(client_id)
    return OAuthConsentSummary(**svc.consent_summary(member, client, scope))


@router.post("/oauth-consent", response_model=OAuthConsentOut)
def grant_consent(
    body: OAuthConsentIn,
    member: CurrentMember = Depends(get_current_member),
    db: Session = Depends(get_db),
) -> OAuthConsentOut:
    """The member approved. Mint the code and hand back the redirect the browser
    should follow — the web app never constructs that URL itself."""
    svc = OAuthService(db)
    client = svc.begin_authorization(
        client_id=body.client_id, redirect_uri=body.redirect_uri,
        response_type="code", code_challenge=body.code_challenge,
        code_challenge_method=body.code_challenge_method,
        scope=body.scope, resource=body.resource)
    code = svc.issue_code(member, client, redirect_uri=body.redirect_uri,
                          code_challenge=body.code_challenge,
                          scope=body.scope, resource=body.resource)
    params = {"code": code}
    if body.state:
        params["state"] = body.state
    # RFC 9207: name the issuer so the client can detect a mix-up attack.
    if body.issuer:
        params["iss"] = body.issuer
    joiner = "&" if "?" in body.redirect_uri else "?"
    return OAuthConsentOut(
        redirect_to=f"{body.redirect_uri}{joiner}{urlencode(params)}")
