"""Parent portal endpoints: the D-13 login, plus curated read-only child views.

Every auth route here is unauthenticated and rate-limited hard — each one is a
probing surface. `/auth/school` and `/auth/find-child` are the roster's front
door (`S-55`/`S-57`), and `/auth/verify-dob` guesses at a ~5,500-value
credential, which is why it also carries the per-student lock (`S-56`) inside
the service.

Everything else requires a parent session (get_current_parent) — staff tokens
are rejected there, and the guardian-link check makes revocation live.
"""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.context import CurrentParent
from app.core.database import get_db
from app.core.dependencies import get_current_parent
from app.core.rate_limit import limiter
from app.schemas.auth import SessionResponse
from app.schemas.common import MessageResponse
from app.schemas.parent import (
    AddChildOut,
    FindChildIn,
    ParentCalendarOut,
    ParentChildMatch,
    ParentChildOut,
    ParentMeOut,
    ParentNotificationsOut,
    ParentReportOut,
    ParentTodayOut,
    RequestOtpIn,
    RequestOtpOut,
    SchoolCodeIn,
    SchoolLookupOut,
    SetCredentialsIn,
    VerifyDobIn,
    VerifyOtpIn,
)
from app.services.parent_auth import ParentAuthService
from app.services.parent_portal import ParentPortalService

router = APIRouter()


# ── D-13 · school code → class → section → child → date of birth ────────────
@router.post("/auth/school", response_model=SchoolLookupOut)
@limiter.limit("20/minute")
def lookup_school(request: Request, body: SchoolCodeIn,
                  db: Session = Depends(get_db)) -> SchoolLookupOut:
    return SchoolLookupOut(**ParentAuthService(db).school_by_code(body.code))


@router.post("/auth/find-child", response_model=list[ParentChildMatch])
@limiter.limit("20/minute")
def find_child(request: Request, body: FindChildIn,
               db: Session = Depends(get_db)) -> list[ParentChildMatch]:
    """`S-55` type-to-search. Rate-limited as well as minimum-length: a search
    box hit a thousand times is a browsable list again."""
    rows = ParentAuthService(db).find_children(body.org_id, body.class_id, body.query)
    return [ParentChildMatch(**r) for r in rows]


@router.post("/auth/verify-dob", response_model=SessionResponse)
@limiter.limit("10/minute")
def verify_dob(request: Request, body: VerifyDobIn,
               db: Session = Depends(get_db)) -> SessionResponse:
    return SessionResponse(
        **ParentAuthService(db).verify_dob(body.student_id, body.date_of_birth))


@router.post("/children/add", response_model=AddChildOut)
@limiter.limit("10/minute")
def add_child(request: Request, body: VerifyDobIn,
              p: CurrentParent = Depends(get_current_parent),
              db: Session = Depends(get_db)) -> AddChildOut:
    """`Q-25` (b) — prove each child once; the sibling switcher then works
    exactly as it does today. The org comes from the verified token (law 1)."""
    return AddChildOut(**ParentAuthService(db).add_child(
        p.user, p.org_id, body.student_id, body.date_of_birth))


@router.post("/auth/request-otp", response_model=RequestOtpOut)
@limiter.limit("5/minute")
def request_otp(request: Request, body: RequestOtpIn,
                db: Session = Depends(get_db)) -> RequestOtpOut:
    return RequestOtpOut(**ParentAuthService(db).request_otp(body.phone))


@router.post("/auth/verify-otp", response_model=SessionResponse)
@limiter.limit("10/minute")
def verify_otp(request: Request, body: VerifyOtpIn,
               db: Session = Depends(get_db)) -> SessionResponse:
    return SessionResponse(**ParentAuthService(db).verify_otp(body.phone, body.code))


@router.post("/auth/credentials", response_model=MessageResponse)
def set_credentials(body: SetCredentialsIn,
                    p: CurrentParent = Depends(get_current_parent),
                    db: Session = Depends(get_db)) -> MessageResponse:
    ParentAuthService(db).set_credentials(
        p.user, username=body.username, email=body.email, password=body.password)
    return MessageResponse(message="Login credentials saved.")


@router.get("/me", response_model=ParentMeOut)
def parent_me(p: CurrentParent = Depends(get_current_parent),
              db: Session = Depends(get_db)) -> ParentMeOut:
    children = ParentAuthService(db).children(p.user_id, p.org_id)
    return ParentMeOut(
        name=p.user.name, phone=p.user.phone, username=p.user.username,
        email=p.user.email, has_password=p.user.password_hash is not None,
        org_name=p.org.name,
        children=[ParentChildOut(**c) for c in children],
    )


@router.get("/children/{student_id}/today", response_model=ParentTodayOut)
def child_today(student_id: uuid.UUID, on_date: date | None = None,
                p: CurrentParent = Depends(get_current_parent),
                db: Session = Depends(get_db)) -> ParentTodayOut:
    return ParentPortalService(db).today(p, student_id, on_date)


@router.get("/children/{student_id}/report", response_model=ParentReportOut)
def child_report(student_id: uuid.UUID,
                 p: CurrentParent = Depends(get_current_parent),
                 db: Session = Depends(get_db)) -> ParentReportOut:
    return ParentPortalService(db).report(p, student_id)


@router.get("/children/{student_id}/calendar", response_model=ParentCalendarOut)
def child_calendar(student_id: uuid.UUID, on_date: date | None = None,
                   p: CurrentParent = Depends(get_current_parent),
                   db: Session = Depends(get_db)) -> ParentCalendarOut:
    """`Q-56` — *"Is school open on Monday?"*, and this child's birthday only."""
    return ParentPortalService(db).calendar(p, student_id, on_date)


# ── D-08 · the notifications archive ────────────────────────────────────────
@router.get("/notifications", response_model=ParentNotificationsOut)
def notifications(p: CurrentParent = Depends(get_current_parent),
                  db: Session = Depends(get_db)) -> ParentNotificationsOut:
    return ParentPortalService(db).notifications(p)


@router.post("/notifications/read", response_model=MessageResponse)
def mark_notifications_read(p: CurrentParent = Depends(get_current_parent),
                            db: Session = Depends(get_db)) -> MessageResponse:
    n = ParentPortalService(db).mark_read(p)
    return MessageResponse(message=f"{n} marked as read.")
