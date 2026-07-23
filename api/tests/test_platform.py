"""Super-admin platform layer: flag gate, create school, enter org."""

import uuid

from sqlalchemy import select

from app.models import Membership, Organization, User
from tests.conftest import AdminSession


def _register(client, cleanup, org_name="Base Org"):
    email = f"op-{uuid.uuid4().hex[:12]}@example.com"
    reg = client.post("/api/v1/auth/register-org",
                      json={"org_name": org_name, "name": "Operator", "email": email,
                            "password": "supersecret1", "timezone": "Asia/Kolkata"}).json()
    cleanup["orgs"].append(uuid.UUID(reg["org"]["id"]))
    cleanup["users"].append(uuid.UUID(reg["user"]["id"]))
    return reg


def _make_super(user_id: str) -> None:
    db = AdminSession()
    try:
        db.get(User, uuid.UUID(user_id)).is_super_admin = True
        db.commit()
    finally:
        db.close()


def test_platform_requires_super_admin(client, cleanup):
    reg = _register(client, cleanup)
    h = {"Authorization": f"Bearer {reg['access_token']}"}
    r = client.get("/api/v1/platform/orgs", headers=h)
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "super_admin_only"
    assert reg["is_super_admin"] is False


def test_create_school_and_enter(client, cleanup):
    reg = _register(client, cleanup)
    _make_super(reg["user"]["id"])
    h = {"Authorization": f"Bearer {reg['access_token']}"}

    # Flag now shows on /me and the org list crosses orgs.
    me = client.get("/api/v1/auth/me", headers=h).json()
    assert me["is_super_admin"] is True
    listed = client.get("/api/v1/platform/orgs", headers=h).json()
    assert any(o["id"] == reg["org"]["id"] for o in listed)

    admin_email = f"owner-{uuid.uuid4().hex[:12]}@example.com"
    created = client.post("/api/v1/platform/orgs", headers=h, json={
        "org_name": "Sunrise School", "timezone": "Asia/Kolkata",
        "admin_name": "Owner", "admin_email": admin_email,
        "admin_password": "handover123"})
    assert created.status_code == 200, created.text
    school = created.json()["org"]
    cleanup["orgs"].append(uuid.UUID(school["id"]))
    db = AdminSession()
    try:
        owner_id = db.scalar(select(User.id).where(User.email == admin_email))
        cleanup["users"].append(owner_id)
        # Operator got an admin membership alongside the school's own admin.
        roles = db.scalars(select(Membership.org_role).where(
            Membership.org_id == uuid.UUID(school["id"]))).all()
        assert roles == ["admin", "admin"]
        assert db.get(Organization, uuid.UUID(school["id"])).name == "Sunrise School"
    finally:
        db.close()
    assert school["member_count"] == 2

    # The handed-over credentials work, and force a password change.
    owner = client.post("/api/v1/auth/login",
                        json={"identifier": admin_email, "password": "handover123"})
    assert owner.status_code == 200, owner.text
    assert owner.json()["must_set_password"] is True
    assert owner.json()["org"]["id"] == school["id"]

    # Enter: a session scoped to the school, as admin.
    entered = client.post(f"/api/v1/platform/orgs/{school['id']}/enter", headers=h)
    assert entered.status_code == 200, entered.text
    assert entered.json()["org"]["id"] == school["id"]
    assert entered.json()["org_role"] == "admin"
    h2 = {"Authorization": f"Bearer {entered.json()['access_token']}"}
    assert client.get("/api/v1/auth/me", headers=h2).json()["org"]["id"] == school["id"]


def test_create_school_rejects_taken_email(client, cleanup):
    reg = _register(client, cleanup)
    _make_super(reg["user"]["id"])
    h = {"Authorization": f"Bearer {reg['access_token']}"}
    r = client.post("/api/v1/platform/orgs", headers=h, json={
        "org_name": "Dup School", "admin_name": "Dup",
        "admin_email": reg["user"]["email"], "admin_password": "handover123"})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "email_taken"
