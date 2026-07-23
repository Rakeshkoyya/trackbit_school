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


def _as_super_admin(client, cleanup):
    """A registered operator, promoted the only way the flag is ever granted."""
    reg = _register(client, cleanup)
    db = AdminSession()
    try:
        db.get(User, uuid.UUID(reg["user"]["id"])).is_super_admin = True
        db.commit()
    finally:
        db.close()
    return {"Authorization": f"Bearer {reg['access_token']}"}


def test_status_and_remark_append_one_history_row(client, cleanup):
    """Status moves and remarks are appended, never overwritten (law 3)."""
    posted = client.post("/api/v1/marketing/demo-requests", json={
        "school_name": "Green Valley", "contact_name": "Latha", "email": "latha@gv.edu",
        "phone": "9222222222", "student_count": 700}).json()
    h = _as_super_admin(client, cleanup)
    rid = posted["id"]

    # remark only — no status move recorded
    r1 = client.post(f"/api/v1/marketing/demo-requests/{rid}/notes",
                     json={"note": "  Called, asked us to ring back Monday.  "}, headers=h)
    assert r1.status_code == 200, r1.text
    assert r1.json()["status"] == "new"
    assert r1.json()["notes"][0]["note"] == "Called, asked us to ring back Monday."
    assert r1.json()["notes"][0]["status_to"] is None
    assert r1.json()["notes"][0]["author_name"] == "Operator"

    # status move with a remark in the same action
    r2 = client.post(f"/api/v1/marketing/demo-requests/{rid}/notes",
                     json={"status": "scheduled", "note": "Demo booked for Friday."}, headers=h)
    assert r2.status_code == 200, r2.text
    detail = r2.json()
    assert detail["status"] == "scheduled"          # cached on the lead
    assert len(detail["notes"]) == 2                # appended, nothing rewritten
    newest = detail["notes"][0]                     # newest first
    assert (newest["status_from"], newest["status_to"]) == ("new", "scheduled")

    # re-selecting the same status is not a move — the remark still lands
    r3 = client.post(f"/api/v1/marketing/demo-requests/{rid}/notes",
                     json={"status": "scheduled", "note": "Confirmed by email."}, headers=h)
    assert r3.status_code == 200, r3.text
    assert r3.json()["notes"][0]["status_to"] is None
    assert len(r3.json()["notes"]) == 3

    # the list view carries the working state without opening the lead
    listed = client.get("/api/v1/marketing/demo-requests", headers=h).json()
    row = next(d for d in listed if d["id"] == rid)
    assert row["status"] == "scheduled"
    assert row["note_count"] == 3
    _drop(rid)


def test_note_rejects_empty_and_unknown_status(client, cleanup):
    posted = client.post("/api/v1/marketing/demo-requests", json={
        "school_name": "Blank Ltd", "contact_name": "B", "email": "b@blank.edu",
        "phone": "9333333333"}).json()
    h = _as_super_admin(client, cleanup)
    rid = posted["id"]

    assert client.post(f"/api/v1/marketing/demo-requests/{rid}/notes",
                       json={"note": "   "}, headers=h).status_code == 422
    assert client.post(f"/api/v1/marketing/demo-requests/{rid}/notes",
                       json={"status": "archived"}, headers=h).status_code == 422
    _drop(rid)


def test_lead_history_is_super_admin_only(client, cleanup):
    posted = client.post("/api/v1/marketing/demo-requests", json={
        "school_name": "Private Eyes", "contact_name": "P", "email": "p@pe.edu",
        "phone": "9444444444"}).json()
    reg = _register(client, cleanup)          # an ordinary org admin
    h = {"Authorization": f"Bearer {reg['access_token']}"}
    rid = posted["id"]

    assert client.get(f"/api/v1/marketing/demo-requests/{rid}").status_code == 401
    denied = client.get(f"/api/v1/marketing/demo-requests/{rid}", headers=h)
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "super_admin_only"
    assert client.post(f"/api/v1/marketing/demo-requests/{rid}/notes",
                       json={"note": "sneaky"}, headers=h).status_code == 403
    _drop(rid)


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
