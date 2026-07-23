"""Public demo-request capture: anyone can post one, only super-admins read them."""

import uuid

from sqlalchemy import delete, select

from app.models import DemoRequest, User
from tests.conftest import AdminSession


def _register(client, cleanup):
    email = f"op-{uuid.uuid4().hex[:12]}@example.com"
    reg = client.post("/api/v1/auth/register-org",
                      json={"org_name": "Base Org", "name": "Operator", "email": email,
                            "password": "supersecret1", "timezone": "Asia/Kolkata"}).json()
    cleanup["orgs"].append(uuid.UUID(reg["org"]["id"]))
    cleanup["users"].append(uuid.UUID(reg["user"]["id"]))
    return reg


def _drop(row_id: str) -> None:
    """demo_requests hangs off no org, so the org cleanup fixture can't reach it."""
    db = AdminSession()
    try:
        db.execute(delete(DemoRequest).where(DemoRequest.id == uuid.UUID(row_id)))
        db.commit()
    finally:
        db.close()


def test_demo_request_public_post(client):
    body = {
        "school_name": "  Sunrise Public School  ", "contact_name": "  Meera R  ",
        "email": "  Meera@Sunrise.EDU  ", "phone": " 9876543210 ", "city": " Guntur ",
        "student_count": 640, "message": "  Hostel of 300.  ", "source": "pricing",
    }
    # No Authorization header at all — this is the one public write.
    r = client.post("/api/v1/marketing/demo-requests", json=body)
    assert r.status_code == 200, r.text
    row_id = r.json()["id"]
    assert r.json()["received"] is True

    db = AdminSession()
    try:
        row = db.get(DemoRequest, uuid.UUID(row_id))
        assert row.school_name == "Sunrise Public School"   # trimmed
        assert row.email == "meera@sunrise.edu"             # normalised
        assert row.city == "Guntur"
        assert row.student_count == 640
        assert row.source == "pricing"
        assert row.status == "new"
    finally:
        db.close()
    _drop(row_id)


def test_demo_request_rejects_bad_input(client):
    r = client.post("/api/v1/marketing/demo-requests", json={
        "school_name": "S", "contact_name": "C", "email": "not-an-email", "phone": "9876543210"})
    assert r.status_code == 422


def test_demo_requests_readable_only_by_super_admin(client, cleanup):
    posted = client.post("/api/v1/marketing/demo-requests", json={
        "school_name": "Vidya Niketan", "contact_name": "Ravi", "email": "ravi@vidya.edu",
        "phone": "9000000000", "student_count": 900}).json()

    reg = _register(client, cleanup)
    h = {"Authorization": f"Bearer {reg['access_token']}"}
    assert client.get("/api/v1/marketing/demo-requests").status_code == 401
    denied = client.get("/api/v1/marketing/demo-requests", headers=h)
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "super_admin_only"

    db = AdminSession()
    try:
        db.get(User, uuid.UUID(reg["user"]["id"])).is_super_admin = True
        db.commit()
    finally:
        db.close()

    listed = client.get("/api/v1/marketing/demo-requests", headers=h)
    assert listed.status_code == 200, listed.text
    assert any(d["id"] == posted["id"] and d["student_count"] == 900
               for d in listed.json())
    _drop(posted["id"])


def test_demo_request_row_carries_no_org(client):
    """A lead exists before its school does — nothing org-scoped may be required."""
    posted = client.post("/api/v1/marketing/demo-requests", json={
        "school_name": "Orgless High", "contact_name": "A", "email": "a@orgless.edu",
        "phone": "9111111111"}).json()
    db = AdminSession()
    try:
        cols = {c.name for c in DemoRequest.__table__.columns}
        assert "org_id" not in cols
        assert db.scalar(select(DemoRequest.id).where(
            DemoRequest.id == uuid.UUID(posted["id"]))) is not None
    finally:
        db.close()
    _drop(posted["id"])
