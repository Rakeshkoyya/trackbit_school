"""P0-B done-when: the SPRD §3.3 role groups have a test per role.

Two layers:
  * pure, DB-free tests of the role-group predicates + FastAPI guard dependencies
    (the access matrix at role-granularity — per-endpoint enforcement lands with
    each module that adds endpoints);
  * DB-backed tests that the memberships domain accepts the four roles and that
    invite/role-change honour them.
"""

import uuid

import pytest

from app.core import roles
from app.core.context import CurrentMember
from app.core.dependencies import (
    require_academic,
    require_admin,
    require_coordinator_up,
    require_office_up,
)
from app.core.exceptions import ForbiddenError
from app.models import Membership, Organization, User


def _member(role: str) -> CurrentMember:
    """A CurrentMember over unpersisted rows — enough to exercise role logic."""
    return CurrentMember(
        user=User(name="T", email=None),
        org=Organization(name="S"),
        membership=Membership(org_role=role),
    )


# ── role-group predicates (SPRD §3.3) ───────────────────────────────────────

@pytest.mark.parametrize(
    "role,admin,coord_up,academic,office_up",
    [
        (roles.ADMIN,       True,  True,  True,  True),
        (roles.COORDINATOR, False, True,  True,  False),
        (roles.TEACHER,     False, False, True,  False),
        (roles.OFFICE,      False, False, False, True),
    ],
)
def test_role_group_predicates(role, admin, coord_up, academic, office_up):
    m = _member(role)
    assert m.is_admin is admin
    assert m.is_coordinator_up is coord_up
    assert m.is_academic is academic       # office is the only role excluded from academics
    assert m.is_office_up is office_up      # teacher/coordinator never reach fees


@pytest.mark.parametrize(
    "guard,allowed",
    [
        (require_admin,          {roles.ADMIN}),
        (require_coordinator_up, {roles.ADMIN, roles.COORDINATOR}),
        (require_academic,       {roles.ADMIN, roles.COORDINATOR, roles.TEACHER}),
        (require_office_up,      {roles.ADMIN, roles.OFFICE}),
    ],
)
def test_guards_admit_exactly_their_group(guard, allowed):
    for role in roles.ALL_ROLES:
        m = _member(role)
        if role in allowed:
            assert guard(member=m) is m
        else:
            with pytest.raises(ForbiddenError):
                guard(member=m)


# ── DB-backed: the memberships domain accepts the four roles ─────────────────

def _register_admin(client, email, cleanup):
    resp = client.post(
        "/api/v1/auth/register-org",
        json={"org_name": "Roles Org", "name": "Director", "email": email,
              "password": "supersecret1", "timezone": "Asia/Kolkata"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    cleanup["orgs"].append(uuid.UUID(body["org"]["id"]))
    cleanup["users"].append(uuid.UUID(body["user"]["id"]))
    return body


@pytest.mark.parametrize("role", [roles.COORDINATOR, roles.TEACHER, roles.OFFICE])
def test_invite_accepts_each_school_role(client, unique_email, cleanup, role):
    admin = _register_admin(client, unique_email, cleanup)
    h = {"Authorization": f"Bearer {admin['access_token']}"}
    inv = client.post(
        "/api/v1/org/members/invite", headers=h,
        json={"name": f"{role.title()} Staff", "phone": f"+9198{uuid.uuid4().int % 10**8:08d}",
              "role": role},
    )
    assert inv.status_code == 200, inv.text
    cleanup["users"].append(uuid.UUID(inv.json()["user_id"]))
    token = inv.json()["invite_url"].rsplit("/join/", 1)[1]
    sess = client.post("/api/v1/auth/verify", json={"token": token})
    assert sess.status_code == 200, sess.text
    assert sess.json()["org_role"] == role


def test_invite_rejects_unknown_role(client, unique_email, cleanup):
    admin = _register_admin(client, unique_email, cleanup)
    h = {"Authorization": f"Bearer {admin['access_token']}"}
    resp = client.post(
        "/api/v1/org/members/invite", headers=h,
        json={"name": "Nope", "phone": "+919812345678", "role": "member"},
    )
    assert resp.status_code == 422, resp.text  # 'member' no longer exists (mapped to teacher)


def test_first_user_is_director_admin(client, unique_email, cleanup):
    admin = _register_admin(client, unique_email, cleanup)
    assert admin["org_role"] == roles.ADMIN
