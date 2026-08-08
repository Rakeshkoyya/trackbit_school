"""The API tier gate (P4) — what a plan actually refuses.

This is the suite that matters for `D-106`: a lock that lives only in the
browser is not a lock. The same data sits behind 420 routes, 45 Lucy tools and
the MCP connector, so a `pro` school must be refused its `max` timesheet by the
*server*, whatever the sidebar happens to render.

Two halves, and the second is the more important one:

- every gated module refuses a school below its tier, naming the tier;
- **every capture surface stays open on Free** (`D-107`). If a test in
  `test_capture_is_never_gated` starts failing, someone has paywalled the
  thing that makes the data exist at all.
"""

import uuid

import pytest

from tests.conftest import set_org_plan

#: This suite IS the gate, so it runs against the real tier map rather than the
#: everything-unlocked default the rest of the suite uses (`conftest._tiers_unlimited`).
pytestmark = pytest.mark.real_tiers


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def org(client, unique_email, cleanup):
    """A brand-new school. Born on Free, like every real one."""
    reg = client.post(
        "/api/v1/auth/register-org",
        json={"org_name": "Gate Co", "name": "Adam Admin", "email": unique_email,
              "password": "supersecret1", "timezone": "Asia/Kolkata"},
    ).json()
    cleanup["orgs"].append(uuid.UUID(reg["org"]["id"]))
    cleanup["users"].append(uuid.UUID(reg["user"]["id"]))
    return {"token": reg["access_token"], "org_id": reg["org"]["id"]}


# (path, feature id, the tier that unlocks it)
GATED = [
    ("/api/v1/boards", "tasks.boards", "max"),
    ("/api/v1/recurring", "tasks.boards", "max"),
    ("/api/v1/staff/directory", "staff.roster", "max"),
    ("/api/v1/staff/work-types", "staff.roster", "max"),
    ("/api/v1/sessions", "sessions.hostel", "max"),
    ("/api/v1/lucy/meta", "agent.lucy", "max"),
    ("/api/v1/fees/structures", "fees.collection", "pro"),
    ("/api/v1/assessments/exam-types", "exams.board", "pro"),
    ("/api/v1/org/oauth-clients", "agent.mcp", "ultra"),
]


@pytest.mark.parametrize(("path", "feature", "tier"), GATED)
def test_a_free_school_is_refused_and_told_which_tier(client, org, path, feature, tier):
    r = client.get(path, headers=_auth(org["token"]))
    assert r.status_code == 402, f"{path} should be tier-gated, got {r.status_code}"
    err = r.json()["error"]
    assert err["code"] == "plan_limit"  # the contract errors.ts already renders
    assert err["details"]["feature"] == feature
    assert err["details"]["required_tier"] == tier
    assert err["details"]["upgrade"] is True


@pytest.mark.parametrize(("path", "feature", "tier"), GATED)
def test_ultra_opens_every_gated_module(client, org, path, feature, tier):
    set_org_plan(org["org_id"], "ultra")
    r = client.get(path, headers=_auth(org["token"]))
    assert r.status_code != 402, f"{path} still gated on ultra: {r.text[:200]}"


def test_pro_opens_pro_but_not_max(client, org):
    """The ladder holds in the middle, not just at the ends."""
    set_org_plan(org["org_id"], "pro")
    assert client.get("/api/v1/fees/structures",
                      headers=_auth(org["token"])).status_code != 402
    r = client.get("/api/v1/staff/directory", headers=_auth(org["token"]))
    assert r.status_code == 402
    assert r.json()["error"]["details"]["required_tier"] == "max"


# ---- D-107: the capture loop is never gated ---------------------------
CAPTURE = [
    "/api/v1/classroom/my-day",
    "/api/v1/classroom/class-log",
    "/api/v1/classroom/homework-log",
    "/api/v1/attendance/my-classes",
    "/api/v1/planner/my-subjects",
    "/api/v1/academics/classes",
    "/api/v1/bands/scope",
    "/api/v1/checks",
    "/api/v1/events/whats-on",
    "/api/v1/reports/daily",
]


@pytest.mark.parametrize("path", CAPTURE)
def test_capture_is_never_gated(client, org, path):
    """`D-107` — free buys the act of recording, in full.

    A free school marks the register, logs the lesson, logs homework, sizes the
    syllabus and runs its ABC programme. Gating any of these would leave the
    paid boards above them permanently empty, so the upgrade could never
    demonstrate its own value. A 4xx for some other reason is fine here; a 402
    is not.
    """
    r = client.get(path, headers=_auth(org["token"]))
    assert r.status_code != 402, f"{path} must stay free (D-107)"


def test_the_school_settings_screen_lists_what_the_plan_includes(client, org):
    s = client.get("/api/v1/org/settings", headers=_auth(org["token"])).json()
    assert "capture.attendance" in s["features"]
    assert "tasks.boards" not in s["features"]

    set_org_plan(org["org_id"], "max")
    s = client.get("/api/v1/org/settings", headers=_auth(org["token"])).json()
    assert "tasks.boards" in s["features"]
    assert "agent.mcp" not in s["features"]  # ultra only


def test_auth_me_carries_the_feature_list(client, org):
    """The browser reads this and never re-derives the tier map."""
    me = client.get("/api/v1/auth/me", headers=_auth(org["token"])).json()
    assert me["org"]["plan"] == "free"
    assert "capture.homework" in me["org"]["features"]
    assert "fees.collection" not in me["org"]["features"]
