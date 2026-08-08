"""Phase 4 billing (P4-BE-01). Razorpay keys aren't needed: we exercise the
webhook (the source of truth) with signed payloads, plus the stub checkout and
non-destructive downgrade.
"""

import hashlib
import hmac
import json
import random
import uuid

import pytest

from app.core.config import settings
from app.models import Organization
from tests.conftest import AdminSession

_WEBHOOK_SECRET = "whsec_test_phase4"


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def _webhook_secret():
    prev = settings.RAZORPAY_WEBHOOK_SECRET
    settings.RAZORPAY_WEBHOOK_SECRET = _WEBHOOK_SECRET
    yield
    settings.RAZORPAY_WEBHOOK_SECRET = prev


@pytest.fixture
def org_ctx(client, unique_email, cleanup):
    reg = client.post(
        "/api/v1/auth/register-org",
        json={"org_name": "Bill Co", "name": "Adam Admin", "email": unique_email,
              "password": "supersecret1", "timezone": "Asia/Kolkata"},
    ).json()
    cleanup["orgs"].append(uuid.UUID(reg["org"]["id"]))
    cleanup["users"].append(uuid.UUID(reg["user"]["id"]))
    # Every org is born `manual` (`D-106`) and the webhook refuses to touch one.
    # These tests are about the gateway-owned path, which in the real flow is
    # entered by completing checkout — so stamp it, as checkout would.
    _set_source(reg["org"]["id"], "billing")
    return {"admin_token": reg["access_token"], "org_id": reg["org"]["id"]}


def _set_source(org_id: str, source: str) -> None:
    db = AdminSession()
    try:
        db.get(Organization, uuid.UUID(org_id)).plan_source = source
        db.commit()
    finally:
        db.close()


def _post_webhook(client, event: str, sub_id: str, *, org_id: str | None = None,
                  current_end: int | None = None, payment: dict | None = None):
    sub_entity = {"id": sub_id}
    if org_id:
        sub_entity["notes"] = {"org_id": org_id}
    if current_end:
        sub_entity["current_end"] = current_end
    payload = {"subscription": {"entity": sub_entity}}
    if payment:
        payload["payment"] = {"entity": payment}
    body = json.dumps({"event": event, "payload": payload}).encode()
    sig = hmac.new(_WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return client.post(
        "/api/v1/billing/webhook", content=body,
        headers={"X-Razorpay-Signature": sig, "Content-Type": "application/json"},
    )


def _plan(org_id: str) -> Organization:
    db = AdminSession()
    try:
        return db.get(Organization, uuid.UUID(org_id))
    finally:
        db.close()


def test_webhook_refuses_a_manually_planned_org(client, org_ctx, _webhook_secret):
    """`D-106` / §1.8 — the trap this guard exists for.

    Every real org today is `manual`: the operator sets its tier by hand. A
    stray or replayed `subscription.cancelled` must not silently downgrade a
    school we just put on ultra. The webhook still answers 200 (Razorpay must
    not retry forever) but changes nothing.
    """
    org_id = org_ctx["org_id"]
    _set_source(org_id, "manual")

    db = AdminSession()
    try:
        org = db.get(Organization, uuid.UUID(org_id))
        org.plan = "ultra"
        db.commit()
    finally:
        db.close()

    r = _post_webhook(client, "subscription.cancelled",
                      f"sub_{uuid.uuid4().hex[:12]}", org_id=org_id)
    assert r.status_code == 200
    assert r.json()["ignored"] == "manual_plan"
    after = _plan(org_id)
    assert after.plan == "ultra", "a manual plan must survive a billing webhook"
    assert after.plan_source == "manual"


def test_webhook_flips_plan_both_directions(client, org_ctx, _webhook_secret):
    org_id = org_ctx["org_id"]
    sub_id = f"sub_{uuid.uuid4().hex[:12]}"

    # Activate -> Pro, with an invoice recorded from the payment entity.
    r = _post_webhook(
        client, "subscription.activated", sub_id, org_id=org_id,
        payment={"id": f"pay_{uuid.uuid4().hex[:10]}", "amount": 50000, "currency": "INR"},
    )
    assert r.status_code == 200
    org = _plan(org_id)
    assert org.plan == "pro" and org.plan_status == "active"

    billing = client.get("/api/v1/billing", headers=_auth(org_ctx["admin_token"])).json()
    assert billing["plan"] == "pro"
    assert len(billing["invoices"]) == 1 and billing["invoices"][0]["amount"] == 50000

    # Cancel -> back to Free, non-destructively.
    r2 = _post_webhook(client, "subscription.cancelled", sub_id)
    assert r2.status_code == 200
    assert _plan(org_id).plan == "free"


def test_webhook_rejects_bad_signature(client, org_ctx, _webhook_secret):
    body = json.dumps({"event": "subscription.activated", "payload": {}}).encode()
    r = client.post(
        "/api/v1/billing/webhook", content=body,
        headers={"X-Razorpay-Signature": "deadbeef", "Content-Type": "application/json"},
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "bad_signature"


def test_failed_payment_enters_grace_then_downgrades(client, org_ctx, _webhook_secret):
    from datetime import UTC, datetime, timedelta

    from app.services import jobs

    org_id = org_ctx["org_id"]
    sub_id = f"sub_{uuid.uuid4().hex[:12]}"
    _post_webhook(client, "subscription.activated", sub_id, org_id=org_id)
    assert _plan(org_id).plan == "pro"

    # A failed charge halts the subscription -> grace (still Pro for now).
    _post_webhook(client, "subscription.halted", sub_id)
    org = _plan(org_id)
    assert org.plan == "pro" and org.plan_status == "grace"

    # Expire the grace window and run the downgrade job.
    db = AdminSession()
    try:
        o = db.get(Organization, uuid.UUID(org_id))
        o.grace_until = datetime.now(UTC) - timedelta(hours=1)
        db.commit()
    finally:
        db.close()
    assert jobs.run_grace_downgrade() >= 1
    assert _plan(org_id).plan == "free"


def test_checkout_stub_when_unconfigured(client, org_ctx):
    # No Razorpay keys in tests -> stub mode: flow wired, checkout disabled.
    r = client.post("/api/v1/billing/checkout", headers=_auth(org_ctx["admin_token"]))
    assert r.status_code == 200
    body = r.json()
    assert body["configured"] is False and body["subscription_id"] is None


def test_downgrade_is_non_destructive(client, org_ctx, _webhook_secret):
    """A Pro org with extra boards keeps every one of them after downgrade.

    `D-109` narrowed what this proves: there is no quota to fall back under any
    more, so the point is purely that a downgrade DELETES NOTHING. Re-locking a
    screen is a tier gate (P4); it never touches rows."""
    org_id = org_ctx["org_id"]
    sub_id = f"sub_{uuid.uuid4().hex[:12]}"
    _post_webhook(client, "subscription.activated", sub_id, org_id=org_id)

    # On Pro: create 3 extra boards.
    for i in range(3):
        assert client.post(
            "/api/v1/boards", headers=_auth(org_ctx["admin_token"]),
            json={"name": f"Extra {i}-{random.randint(0, 9999)}"},
        ).status_code == 200

    boards_before = client.get("/api/v1/boards", headers=_auth(org_ctx["admin_token"])).json()
    total_before = len(boards_before["my_boards"]) + len(boards_before["other_public"])

    _post_webhook(client, "subscription.cancelled", sub_id)
    assert _plan(org_id).plan == "free"

    boards_after = client.get("/api/v1/boards", headers=_auth(org_ctx["admin_token"])).json()
    total_after = len(boards_after["my_boards"]) + len(boards_after["other_public"])
    assert total_after == total_before  # nothing deleted

    # ...and still works afterwards: a downgrade re-locks screens, it does not
    # meter what is left behind them (`D-109`).
    assert client.post(
        "/api/v1/boards", headers=_auth(org_ctx["admin_token"]),
        json={"name": f"OneMore-{random.randint(0, 9999)}"},
    ).status_code == 200
