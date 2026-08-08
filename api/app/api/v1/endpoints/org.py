"""Org endpoints: members list / invite / role change / removal (P1-BE-08)."""

import uuid

from fastapi import APIRouter, Depends, File, Query, Request, Response, UploadFile
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.database import get_db
from app.core.dependencies import get_current_member, require_admin
from app.core.rate_limit import limiter
from app.schemas.ingest import AnalyzeOut, StaffCommitIn, StaffCommitOut
from app.schemas.org import (
    AdminResetPasswordRequest,
    AdminResetPasswordResponse,
    BulkMembersRequest,
    BulkMembersResponse,
    InvitedMemberResponse,
    InviteMemberRequest,
    MemberOut,
    MembersListResponse,
    OrgSettingsOut,
    OrgSettingsUpdate,
    RemoveMemberResponse,
    RoleUpdateRequest,
    UsernameAvailabilityResponse,
)
from app.schemas.report import NudgeResponse, OrgDashboardResponse
from app.schemas.tiers import OrgPlanOut, UpgradeRequestIn, UpgradeRequestOut
from app.services import staff_import, templates
from app.services.member import MemberService
from app.services.nudge import NudgeService
from app.services.org import OrgService
from app.services.reports import ReportService
from app.services.staff_import import StaffImporter
from app.services.tiers import TierService

router = APIRouter()


# ---- the school's own plan (`D-106`) ----------------------------------
# Ungated on purpose: a school must always be able to see what it is on and what
# the next tier costs. Paywalling the paywall would be absurd.
@router.get("/plan", response_model=OrgPlanOut)
def get_plan(
    member=Depends(get_current_member), db: Session = Depends(get_db)
) -> OrgPlanOut:
    """What each tier costs THIS school, plus any request already in flight.

    Every upgrade wall reads this, which is why the quote carries the school's
    own student count: the wall shows its working ("₹25 × 480 students") rather
    than a number the school has to take on faith.
    """
    service = TierService(db)
    open_request = service.open_request(member.org_id)
    return OrgPlanOut(
        quote=service.quote(member.org),
        open_request=service.request_summary(open_request) if open_request else None,
        can_request=member.is_admin,
    )


@router.post("/plan/request", response_model=UpgradeRequestOut)
def request_upgrade(
    body: UpgradeRequestIn,
    member=Depends(get_current_member),
    db: Session = Depends(get_db),
) -> UpgradeRequestOut:
    """Ask to be moved up a tier. There is no gateway: this reaches the
    operator, who phones the school and sets the plan by hand.

    Deliberately NOT `require_admin`. The service raises 403 `admin_only` with
    copy a teacher can act on, so the wall renders "contact your admin" from the
    same response rather than a bare permission error.
    """
    return TierService(db).raise_request(member, body)


# ── staff document import (V2-P7, SPRD2 §5.1) ────────────────────────────────
@router.get("/members/import/template")
def staff_import_template(_: CurrentMember = Depends(require_admin)):
    """V1-2 §6 ②: blank staff template, generated from the importer's SPECS."""
    return Response(
        content=templates.staff_template(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="staff-template.xlsx"'})


@router.post("/members/import/analyze", response_model=AnalyzeOut)
async def staff_import_analyze(file: UploadFile = File(...),
                               _: CurrentMember = Depends(require_admin)):
    """Parse a staff sheet: proposed mapping + the gaps a human must close."""
    return staff_import.analyze(await file.read())


@router.post("/members/import/commit", response_model=StaffCommitOut)
def staff_import_commit(body: StaffCommitIn, m: CurrentMember = Depends(require_admin),
                        db: Session = Depends(get_db)):
    return StaffImporter(db).commit(
        m, mapping=body.mapping, rows=body.rows, academic_year_id=body.academic_year_id,
        default_password=body.default_password)


@router.get("/settings", response_model=OrgSettingsOut)
def get_settings(
    member: CurrentMember = Depends(get_current_member), db: Session = Depends(get_db)
) -> OrgSettingsOut:
    return OrgService(db).settings(member)


@router.patch("/settings", response_model=OrgSettingsOut)
def update_settings(
    body: OrgSettingsUpdate,
    admin: CurrentMember = Depends(require_admin),
    db: Session = Depends(get_db),
) -> OrgSettingsOut:
    return OrgService(db).update(admin, body)


@router.get("/dashboard", response_model=OrgDashboardResponse)
def org_dashboard(
    range: str = Query("today", pattern="^(today|week)$"),
    admin: CurrentMember = Depends(require_admin),
    db: Session = Depends(get_db),
) -> OrgDashboardResponse:
    return ReportService(db).org_dashboard(admin.org_id, admin.org.timezone, range)


@router.post("/nudge/{user_id}", response_model=NudgeResponse)
def nudge_member(
    user_id: uuid.UUID,
    admin: CurrentMember = Depends(require_admin),
    db: Session = Depends(get_db),
) -> NudgeResponse:
    return NudgeService(db).nudge(admin, user_id)


@router.get("/members", response_model=MembersListResponse)
def list_members(
    member: CurrentMember = Depends(get_current_member), db: Session = Depends(get_db)
) -> MembersListResponse:
    # Any member can see the roster (open model); only admins mutate it.
    return MemberService(db).list_members(member)


@router.get("/members/username-available", response_model=UsernameAvailabilityResponse)
def username_available(
    username: str = Query(..., min_length=1, max_length=64),
    admin: CurrentMember = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UsernameAvailabilityResponse:
    # Static path declared before the dynamic /members/{user_id} routes so it
    # isn't shadowed. Admin-only: it powers the bulk-add grid's live check.
    return UsernameAvailabilityResponse(**MemberService(db).check_username(username))


@router.post("/members/invite", response_model=InvitedMemberResponse)
@limiter.limit("30/minute")
def invite_member(
    request: Request,
    body: InviteMemberRequest,
    admin: CurrentMember = Depends(require_admin),
    db: Session = Depends(get_db),
) -> InvitedMemberResponse:
    result = MemberService(db).invite(
        admin, name=body.name, email=body.email, phone=body.phone,
        role=body.role, mode=body.mode,
    )
    return InvitedMemberResponse(**result)


@router.patch("/members/{user_id}/role", response_model=MemberOut)
def change_member_role(
    user_id: uuid.UUID,
    body: RoleUpdateRequest,
    admin: CurrentMember = Depends(require_admin),
    db: Session = Depends(get_db),
) -> MemberOut:
    return MemberService(db).change_role(admin, user_id, body.role)


@router.delete("/members/{user_id}", response_model=RemoveMemberResponse)
def remove_member(
    user_id: uuid.UUID,
    admin: CurrentMember = Depends(require_admin),
    db: Session = Depends(get_db),
) -> RemoveMemberResponse:
    orphaned = MemberService(db).remove(admin, user_id)
    return RemoveMemberResponse(orphaned_tasks=orphaned)


@router.post("/members/bulk", response_model=BulkMembersResponse)
@limiter.limit("10/minute")
def bulk_create_members(
    request: Request,
    body: BulkMembersRequest,
    admin: CurrentMember = Depends(require_admin),
    db: Session = Depends(get_db),
) -> BulkMembersResponse:
    return MemberService(db).bulk_create(admin, body.members)


@router.post("/members/{user_id}/reset-password", response_model=AdminResetPasswordResponse)
def admin_reset_password(
    user_id: uuid.UUID,
    body: AdminResetPasswordRequest,
    admin: CurrentMember = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AdminResetPasswordResponse:
    return MemberService(db).admin_reset_password(admin, user_id, body.password)
