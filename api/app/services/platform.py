"""Platform service (super-admin): the layer above orgs.

Every method here runs with the RLS org scope lifted (require_super_admin) and
crosses org boundaries ON PURPOSE — this is the one module where that is the
job, not a leak. Nothing in here is reachable without users.is_super_admin.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.exceptions import ConflictError, NotFoundError
from app.core.security import hash_password
from app.models import (
    AcademicYear,
    Board,
    BoardMember,
    Membership,
    Organization,
    SchoolClass,
    Student,
    User,
)
from app.schemas.platform import CreateSchoolRequest, CreateSchoolResult, PlatformOrgOut
from app.services.auth import AuthService


class PlatformService:
    def __init__(self, db: Session):
        self.db = db

    def _set_org_scope(self, value: str) -> None:
        self.db.execute(
            text("SELECT set_config('app.current_org_id', :v, true)"), {"v": value})

    # ── list ─────────────────────────────────────────────────────────────────
    def list_orgs(self) -> list[PlatformOrgOut]:
        """Every school, newest first, with the counts the operator scans for."""
        member_counts = dict(self.db.execute(
            select(Membership.org_id, func.count(Membership.id))
            .where(Membership.status == "active").group_by(Membership.org_id)).all())
        student_counts = dict(self.db.execute(
            select(Student.org_id, func.count(Student.id))
            .where(Student.status == "active").group_by(Student.org_id)).all())
        class_counts = dict(self.db.execute(
            select(SchoolClass.org_id, func.count(SchoolClass.id))
            .group_by(SchoolClass.org_id)).all())
        active_years = dict(self.db.execute(
            select(AcademicYear.org_id, func.min(AcademicYear.label))
            .where(AcademicYear.is_active.is_(True)).group_by(AcademicYear.org_id)).all())
        last_actives = dict(self.db.execute(
            select(Membership.org_id, func.max(Membership.last_active_at))
            .group_by(Membership.org_id)).all())

        return [
            PlatformOrgOut(
                id=o.id, name=o.name, timezone=o.timezone, plan=o.plan,
                created_at=o.created_at,
                member_count=member_counts.get(o.id, 0),
                student_count=student_counts.get(o.id, 0),
                class_count=class_counts.get(o.id, 0),
                active_year=active_years.get(o.id),
                last_active_at=last_actives.get(o.id),
            )
            for o in self.db.scalars(
                select(Organization).order_by(Organization.created_at.desc()))
        ]

    def _org_out(self, org: Organization) -> PlatformOrgOut:
        return next(o for o in self.list_orgs() if o.id == org.id)

    # ── create ───────────────────────────────────────────────────────────────
    def create_school(self, operator: CurrentMember,
                      body: CreateSchoolRequest) -> CreateSchoolResult:
        """Org + its first admin (temp password, forced change on first login) +
        an admin membership for the operator, so they can enter and run setup."""
        if self.db.scalar(select(User).where(User.email == body.admin_email)) is not None:
            raise ConflictError("An account with this email already exists.",
                                code="email_taken")

        org = Organization(name=body.org_name, timezone=body.timezone)
        self.db.add(org)
        self.db.flush()
        # New rows belong to the NEW org; point RLS there for the WITH CHECK policies.
        self._set_org_scope(str(org.id))

        admin = User(name=body.admin_name, email=body.admin_email,
                     password_hash=hash_password(body.admin_password),
                     must_set_password=True)
        self.db.add(admin)
        self.db.flush()
        self.db.add(Membership(org_id=org.id, user_id=admin.id, org_role="admin"))
        # The operator joins as admin too — that is how setup gets done before handover.
        self.db.add(Membership(org_id=org.id, user_id=operator.user_id, org_role="admin",
                               last_active_at=datetime.now(UTC)))
        # Same starter board every org gets on registration (Home is never bare).
        general = Board(org_id=org.id, name="General", visibility="public",
                        category="tasks", created_by=admin.id, owner_id=admin.id)
        self.db.add(general)
        self.db.flush()
        self.db.add(BoardMember(board_id=general.id, user_id=admin.id))
        self.db.flush()
        self._set_org_scope("")
        return CreateSchoolResult(org=self._org_out(org),
                                  admin_email=body.admin_email,
                                  admin_name=body.admin_name)

    # ── enter ────────────────────────────────────────────────────────────────
    def enter_org(self, operator: CurrentMember, org_id: uuid.UUID) -> dict:
        """A session scoped to any school — ensuring an admin membership first,
        then riding the ordinary switch-org flow (token stays the only carrier
        of org context)."""
        org = self.db.get(Organization, org_id)
        if org is None:
            raise NotFoundError("Organization")
        membership = self.db.scalar(select(Membership).where(
            Membership.org_id == org_id, Membership.user_id == operator.user_id))
        if membership is None:
            self._set_org_scope(str(org_id))
            membership = Membership(org_id=org_id, user_id=operator.user_id,
                                    org_role="admin")
            self.db.add(membership)
            self.db.flush()
        elif membership.status != "active":
            membership.status = "active"
            self.db.flush()
        return AuthService(self.db).switch_org(operator.user, org_id)
