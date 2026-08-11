"""The operator's setup flow (SETUP-REDESIGN-PLAN §5, phase P5).

One school, one workbook, one screen:

    template → (the school fills it in) → review → import → readiness → handover

Only the platform operator reaches any of this. Schools do not self-onboard —
founder decision 2026-07-20, made real on the wire here rather than only in the
navigation, which is where it lived until now.

**Why this service exists rather than the endpoints calling the pack directly:**
`require_super_admin` blanks the request's RLS org scope, which is right for
cross-org platform reads and wrong for writing inside one school — every
`WITH CHECK` policy would reject the insert. So the operator has to be *placed*
into the target org first: an admin membership, and the GUC pointed at that org.
`PlatformService.create_school` already does exactly this dance for the org it
creates; `_context` is the same move for an org that already exists.
"""

import uuid

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.exceptions import NotFoundError, ValidationError
from app.models import Membership, Organization, User
from app.schemas.setup_pack import (
    CredentialOut,
    FindingOut,
    PackImportOut,
    PackReviewOut,
    SheetResultOut,
    SheetSummaryOut,
    StaffLoginIn,
    StaffLoginRowOut,
    StaffLoginsResult,
)
from app.services.setup_pack import (
    BLOCKER,
    NOTE,
    WARNING,
    PackCommitter,
    ParsedPack,
    ValidationReport,
    build_pack,
    build_welcome,
    filename_for,
    parse_pack,
    validate,
    welcome_filename,
)
from app.services.setup_pack.logins import StaffLoginService

# A whole school in one workbook is small — the biggest realistic pack is a few
# thousand student rows. Anything far past that is a mistake or an attack, and
# openpyxl will happily spend minutes on it.
MAX_PACK_BYTES = 12 * 1024 * 1024


class SchoolSetupService:
    def __init__(self, db: Session):
        self.db = db

    # ── context ──────────────────────────────────────────────────────────────
    def _org(self, org_id: uuid.UUID) -> Organization:
        org = self.db.get(Organization, org_id)
        if org is None:
            raise NotFoundError("Organization")
        return org

    def _context(self, operator: CurrentMember, org_id: uuid.UUID) -> CurrentMember:
        """The operator, acting inside one school.

        Ensures the admin membership (same rule as `enter_org`: the operator is a
        member of every school they set up, and `core/staff.py::not_operator`
        keeps them off the staff roster while leaving permission reads intact),
        then points RLS at that org so the inserts pass their WITH CHECK.
        """
        org = self._org(org_id)
        self.db.execute(
            text("SELECT set_config('app.current_org_id', :v, true)"),
            {"v": str(org_id)})
        membership = self.db.scalar(select(Membership).where(
            Membership.org_id == org_id,
            Membership.user_id == operator.user_id))
        if membership is None:
            membership = Membership(org_id=org_id, user_id=operator.user_id,
                                    org_role="admin")
            self.db.add(membership)
            self.db.flush()
        elif membership.status != "active":
            membership.status = "active"
            self.db.flush()
        return CurrentMember(user=operator.user, org=org, membership=membership)

    # ── 1a. the staff logins, before they are handed over ────────────────────
    # Delegated whole to `setup_pack/logins.py`; what lives here is the org
    # context — `_context` is what points RLS at the school and what makes the
    # operator a member of it, and a write done without that is a write the
    # policies refuse.
    def staff_logins(self, org_id: uuid.UUID) -> list[StaffLoginRowOut]:
        self._org(org_id)
        return StaffLoginService(self.db).list_logins(org_id)

    def save_staff_logins(
        self, operator: CurrentMember, org_id: uuid.UUID, logins: list[StaffLoginIn]
    ) -> StaffLoginsResult:
        member = self._context(operator, org_id)
        return StaffLoginService(self.db).save(member, org_id, logins)

    # ── 1. the blank pack ────────────────────────────────────────────────────
    def template(self, org_id: uuid.UUID) -> tuple[bytes, str]:
        """Pre-filled with what the operator already typed when creating the
        school, so nobody is asked for the same fact twice."""
        org = self._org(org_id)
        overrides = {k: v for k, v in (
            ("school_name", org.name), ("address", org.address),
            ("state", org.state), ("board", org.board)) if v}
        return build_pack(org.name, overrides=overrides), filename_for(org.name)

    # ── 1b. the handover sheet ───────────────────────────────────────────────
    def welcome(self, org_id: uuid.UUID) -> tuple[bytes, str]:
        """The page the school keeps: who signs in where, and the line between
        what they change and what they ask us for."""
        org = self._org(org_id)
        logins = [
            (user.name, user.email or user.username or "—")
            for membership, user in self.db.execute(
                select(Membership, User)
                .join(User, User.id == Membership.user_id)
                .where(Membership.org_id == org_id,
                       Membership.org_role == "admin",
                       Membership.status == "active")).all()
            # The operator is a member of every school they set up but is not
            # the school's admin — `core/staff.py::not_operator`, same rule.
            if not user.is_super_admin
        ]
        return (
            build_welcome(school_name=org.name, school_code=org.school_code,
                          admin_logins=logins,
                          parent_portal_enabled=bool(org.parent_portal_enabled)),
            welcome_filename(org.name))

    # ── 2. review — nothing is written ───────────────────────────────────────
    def review(self, org_id: uuid.UUID, data: bytes) -> PackReviewOut:
        self._org(org_id)
        pack = self._parse(data)
        return self._review_out(pack, validate(pack))

    def _parse(self, data: bytes) -> ParsedPack:
        if not data:
            raise ValidationError("No file was uploaded.")
        if len(data) > MAX_PACK_BYTES:
            raise ValidationError(
                "That file is too large to be a setup pack. If it really is one, "
                "send it to us directly.")
        try:
            return parse_pack(data)
        except Exception as exc:  # openpyxl raises a zoo of types on bad input
            raise ValidationError(
                "Couldn't open that file. It needs to be the .xlsx setup pack — "
                "not a PDF, a .csv, or a Google Sheets link."
            ) from exc

    def _review_out(self, pack: ParsedPack,
                    report: ValidationReport) -> PackReviewOut:
        return PackReviewOut(
            ready=report.ready,
            findings=[FindingOut(sheet=f.sheet, severity=f.severity,
                                 message=f.message, fix=f.fix, row=f.row,
                                 rule=f.rule)
                      for f in report.findings],
            summaries=[SheetSummaryOut(key=s.key, title=s.title, present=s.present,
                                       rows=s.rows, blocked_rows=s.blocked_rows)
                       for s in report.summaries],
            blockers=len(report.of(BLOCKER)),
            warnings=len(report.of(WARNING)),
            notes=len(report.of(NOTE)),
            total_rows=pack.total_rows,
            missing_sheets=pack.missing_sheets,
            extra_sheets=pack.extra_sheets)

    # ── 3. import — one transaction ──────────────────────────────────────────
    def import_pack(self, operator: CurrentMember, org_id: uuid.UUID, data: bytes,
                    *, replace_syllabus: bool = False) -> PackImportOut:
        """Validate again on the way in, then write.

        Re-validating is not paranoia about the client: the operator reviews one
        file and can upload a different one a minute later, and importing a pack
        nobody read the report for is exactly how a school gets built wrong.
        """
        pack = self._parse(data)
        report = validate(pack)
        review = self._review_out(pack, report)
        if not report.ready:
            return PackImportOut(imported=False, review=review)

        member = self._context(operator, org_id)
        result = PackCommitter(self.db).commit(
            member, pack, replace_syllabus=replace_syllabus)
        return PackImportOut(
            imported=True, review=review,
            sheets=[SheetResultOut(key=s.key, title=s.title, created=s.created,
                                   updated=s.updated, skipped=s.skipped,
                                   notes=s.notes)
                    for s in result.sheets],
            credentials=[CredentialOut(user_id=c["user_id"], name=c["name"],
                                       username=c["username"],
                                       password=c["password"])
                         for c in result.credentials])
