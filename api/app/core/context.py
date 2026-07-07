"""Authenticated request context."""

import uuid
from dataclasses import dataclass

from app.core import roles
from app.models import Membership, Organization, User


@dataclass
class CurrentMember:
    """Resolved auth context for the current request.

    org_id always comes from here (the verified token), never from request
    params — that is the one architectural law (plan §7.3).
    """

    user: User
    org: Organization
    membership: Membership

    @property
    def user_id(self) -> uuid.UUID:
        return self.user.id

    @property
    def org_id(self) -> uuid.UUID:
        return self.org.id

    @property
    def org_role(self) -> str:
        return self.membership.org_role

    @property
    def is_admin(self) -> bool:
        return self.membership.org_role == roles.ADMIN

    @property
    def is_coordinator(self) -> bool:
        return self.membership.org_role == roles.COORDINATOR

    @property
    def is_teacher(self) -> bool:
        return self.membership.org_role == roles.TEACHER

    @property
    def is_office(self) -> bool:
        return self.membership.org_role == roles.OFFICE

    # Role-group predicates mirroring the permission dependencies (SPRD §3.3).
    @property
    def is_coordinator_up(self) -> bool:
        return self.membership.org_role in roles.COORDINATOR_UP

    @property
    def is_academic(self) -> bool:
        """Any academic-facing role (admin/coordinator/teacher) — never office."""
        return self.membership.org_role in roles.ACADEMIC

    @property
    def is_office_up(self) -> bool:
        return self.membership.org_role in roles.OFFICE_UP
