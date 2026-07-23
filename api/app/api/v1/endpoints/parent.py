"""Parent portal endpoints: phone-OTP auth + curated read-only child views.

The auth pair is unauthenticated and rate-limited hard (OTP request is an SMS/
WhatsApp spend and a probing surface). Everything else requires a parent
session (get_current_parent) — staff tokens are rejected there, and the
guardian-link check makes revocation live.
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
    ParentChildOut,
    ParentMeOut,
    ParentReportOut,
    ParentTodayOut,
    RequestOtpIn,
    RequestOtpOut,
    SetCredentialsIn,
    VerifyOtpIn,
)
from app.services.parent_auth import ParentAuthService
from app.services.parent_portal import ParentPortalService

router = APIRouter()


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
