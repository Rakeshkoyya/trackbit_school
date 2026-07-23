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
    def is_teacher(self) -> bool:
        return self.membership.org_role == roles.TEACHER

    # Role-group predicates mirroring the permission dependencies (SPRD v2 §2:
    # coordinator_up/office_up are both admin-only; academic = every member).
    @property
    def is_coordinator_up(self) -> bool:
        return self.membership.org_role in roles.COORDINATOR_UP

    @property
    def is_academic(self) -> bool:
        """Any member — in v2 every role (admin/teacher) is academic staff."""
        return self.membership.org_role in roles.ACADEMIC

    @property
    def is_office_up(self) -> bool:
        return self.membership.org_role in roles.OFFICE_UP


@dataclass
class CurrentParent:
    """Resolved parent auth context (parent portal): a guardian user plus the
    active students their claimed guardian rows link to in this org.

    Not a CurrentMember — parents have no membership and no staff role; staff
    guards never accept a parent token and vice versa. org_id still comes only
    from the verified token (law 1)."""

    user: "User"
    org: Organization
    students: list  # active Student rows in this org, the parent's children

    @property
    def user_id(self) -> uuid.UUID:
        return self.user.id

    @property
    def org_id(self) -> uuid.UUID:
        return self.org.id

    def child_ids(self) -> set[uuid.UUID]:
        return {s.id for s in self.students}
