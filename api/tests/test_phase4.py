"""Phase 4 — the F9 lifecycle edge table, plus the `D-109` quota removal.

Pure logic (no Razorpay/R2), so it verifies end-to-end through the HTTP stack.
The tier gate itself lives in `test_features.py`; what is asserted here is that
the *old* Free/Pro metering is gone and stays gone.
"""

import random
import uuid

import pytest

from app.models import Notification
from tests.conftest import AdminSession


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _rand_phone() -> str:
    return "+9198" + "".join(random.choices("0123456789", k=8))


@pytest.fixture
def org_ctx(client, unique_email, cleanup):
    reg = client.post(
        "/api/v1/auth/register-org",
        json={"org_name": "Ops Co", "name": "Adam Admin", "email": unique_email,
              "password": "supersecret1", "timezone": "Asia/Kolkata"},
    ).json()
    cleanup["orgs"].append(uuid.UUID(reg["org"]["id"]))
    cleanup["users"].append(uuid.UUID(reg["user"]["id"]))
    admin_token = reg["access_token"]

    def invite(name, role="teacher"):
        inv = client.post(
            "/api/v1/org/members/invite", headers=_auth(admin_token),
            json={"name": name, "phone": _rand_phone(), "role": role},
        ).json()
        if "user_id" in inv:
            cleanup["users"].append(uuid.UUID(inv["user_id"]))
        return inv

    def join(inv):
        token = inv["invite_url"].rsplit("/join/", 1)[1]
        return client.post("/api/v1/auth/verify", json={"token": token}).json()["access_token"]

    bob = invite("Bob")
    bob_token = join(bob)
    board = client.post(
        "/api/v1/boards", headers=_auth(admin_token),
        json={"name": "Ops", "visibility": "public"},
    ).json()
    return {
        "admin_token": admin_token, "admin_id": reg["user"]["id"], "org_id": reg["org"]["id"],
        "bob_id": bob["user_id"], "bob_token": bob_token, "board_id": board["id"],
        "invite": invite, "join": join,
    }


# ---- D-109: the inherited Free/Pro quotas are gone ---------------------
# These three used to assert the caps. They now assert their ABSENCE, which is
# the regression that matters: Tasks is all-or-nothing behind
# `Feature.TASKS_BOARDS` (max), so a school that can reach the module is never
# metered inside it. Re-introducing a quota should break these.
def test_no_board_quota(client, org_ctx):
    # The old Free plan stopped at 2 boards; register made "General" and the
    # fixture made "Ops", so under the old rule the first of these would 402.
    for name in ("Third", "Fourth", "Fifth"):
        resp = client.post(
            "/api/v1/boards", headers=_auth(org_ctx["admin_token"]),
            json={"name": name, "visibility": "public"},
        )
        assert resp.status_code == 200, resp.text


def test_no_member_seat_cap(client, org_ctx):
    # 8 active members was the old ceiling — a number no school is. Admin + Bob
    # are already active, so this takes the org well past it.
    for i in range(9):
        inv = org_ctx["invite"](f"Hire {i}")
        assert "user_id" in inv, inv


def test_critical_task_is_not_gated(client, org_ctx):
    resp = client.post(
        "/api/v1/tasks", headers=_auth(org_ctx["admin_token"]),
        json={"board_id": org_ctx["board_id"], "title": "Alarm me", "is_critical": True},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["is_critical"] is True


def test_org_settings_get_and_update(client, org_ctx):
    s = client.get("/api/v1/org/settings", headers=_auth(org_ctx["admin_token"])).json()
    assert s["plan"] == "free"
    # The payload carries a computed feature list rather than a tier name the
    # client would have to map itself. What it CONTAINS per tier is asserted in
    # `test_feature_gate.py`, which runs against the real map — this suite runs
    # with tiers unlocked (see `conftest._tiers_unlimited`).
    assert isinstance(s["features"], list) and s["features"]
    assert s["usage"]["boards"] == 2  # General + Ops

    upd = client.patch(
        "/api/v1/org/settings", headers=_auth(org_ctx["admin_token"]),
        json={"name": "Ops Co Renamed", "report_card_hour": 19},
    ).json()
    assert upd["name"] == "Ops Co Renamed" and upd["report_card_hour"] == 19

    # Members can't change org settings.
    assert client.patch(
        "/api/v1/org/settings", headers=_auth(org_ctx["bob_token"]),
        json={"name": "Nope"},
    ).status_code == 403


# ---- F9 lifecycle -----------------------------------------------------
def test_board_ownership_transfers_when_owner_removed(client, org_ctx):
    bea = org_ctx["invite"]("Bea", role="admin")
    bea_token = org_ctx["join"](bea)
    bea_board = client.post(
        "/api/v1/boards", headers=_auth(bea_token),
        json={"name": "Bea's board", "visibility": "public"},
    ).json()
    assert bea_board["owner_id"] == bea["user_id"]

    # Remove Bea — her board's ownership transfers to the oldest admin (Adam).
    assert client.delete(
        f"/api/v1/org/members/{bea['user_id']}", headers=_auth(org_ctx["admin_token"])
    ).status_code == 200
    after = client.get(f"/api/v1/boards/{bea_board['id']}", headers=_auth(org_ctx["admin_token"])).json()
    assert after["owner_id"] == org_ctx["admin_id"]
    assert after["can_manage"] is True


def test_orphaned_tasks_flagged_on_dashboard(client, org_ctx):
    client.post(
        "/api/v1/tasks", headers=_auth(org_ctx["admin_token"]),
        json={"board_id": org_ctx["board_id"], "title": "Bob's job", "assignee_id": org_ctx["bob_id"]},
    )
    client.delete(f"/api/v1/org/members/{org_ctx['bob_id']}", headers=_auth(org_ctx["admin_token"]))
    dash = client.get("/api/v1/org/dashboard", headers=_auth(org_ctx["admin_token"])).json()
    assert dash["orphaned_count"] >= 1


def test_public_to_private_unassigns_and_notifies(client, org_ctx):
    t = client.post(
        "/api/v1/tasks", headers=_auth(org_ctx["admin_token"]),
        json={"board_id": org_ctx["board_id"], "title": "Shared task", "assignee_id": org_ctx["bob_id"]},
    ).json()
    # Flip Ops to private — Bob isn't a board member, so his task is unassigned.
    client.patch(
        f"/api/v1/boards/{org_ctx['board_id']}", headers=_auth(org_ctx["admin_token"]),
        json={"visibility": "private"},
    )
    detail = client.get(f"/api/v1/tasks/{t['id']}", headers=_auth(org_ctx["admin_token"])).json()
    assert detail["assignee"] is None

    db = AdminSession()
    try:
        from sqlalchemy import select

        notes = list(db.scalars(
            select(Notification).where(
                Notification.user_id == uuid.UUID(org_ctx["bob_id"]),
                Notification.notif_type == "unassigned",
            )
        ))
        assert len(notes) >= 1
    finally:
        db.close()


def test_template_delete_keeps_history_edit_is_future_only(client, org_ctx):
    tmpl = client.post(
        "/api/v1/recurring", headers=_auth(org_ctx["admin_token"]),
        json={"board_id": org_ctx["board_id"], "title": "Daily standup",
              "recurrence": {"freq": "daily"}},
    ).json()
    # Create materializes today+tomorrow, so an instance exists now.
    tasks = client.get(
        f"/api/v1/boards/{org_ctx['board_id']}/tasks", headers=_auth(org_ctx["admin_token"])
    ).json()
    assert any(t["title"] == "Daily standup" for t in tasks)

    # Edit title — existing instances must NOT be rewritten (F9: future only).
    client.patch(
        f"/api/v1/recurring/{tmpl['id']}", headers=_auth(org_ctx["admin_token"]),
        json={"title": "Daily standup v2"},
    )
    tasks2 = client.get(
        f"/api/v1/boards/{org_ctx['board_id']}/tasks", headers=_auth(org_ctx["admin_token"])
    ).json()
    assert any(t["title"] == "Daily standup" for t in tasks2)  # old instance unchanged

    # Delete template — past instances and their history remain.
    assert client.delete(
        f"/api/v1/recurring/{tmpl['id']}", headers=_auth(org_ctx["admin_token"])
    ).status_code == 200
    tasks3 = client.get(
        f"/api/v1/boards/{org_ctx['board_id']}/tasks", headers=_auth(org_ctx["admin_token"])
    ).json()
    assert any(t["title"] == "Daily standup" for t in tasks3)


def test_template_pause_stops_new_instances(client, org_ctx):
    from datetime import timedelta

    from app.core.timeutil import org_day_bounds
    from app.models import Organization, TaskTemplate
    from app.services.recurrence import RecurringService

    tmpl = client.post(
        "/api/v1/recurring", headers=_auth(org_ctx["admin_token"]),
        json={"board_id": org_ctx["board_id"], "title": "Paused job",
              "recurrence": {"freq": "daily"}},
    ).json()
    client.post(
        f"/api/v1/recurring/{tmpl['id']}/toggle?active=false", headers=_auth(org_ctx["admin_token"])
    )

    db = AdminSession()
    try:
        org = db.get(Organization, uuid.UUID(org_ctx["org_id"]))
        _, _, now_local = org_day_bounds(org.timezone)
        future = now_local.date() + timedelta(days=5)
        t = db.get(TaskTemplate, uuid.UUID(tmpl["id"]))
        created = RecurringService(db)._materialize_template(t, org, [future])
        assert created == 0  # paused -> no new instances
    finally:
        db.close()
