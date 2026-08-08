"""Agent connector credentials — Phase 2 (`D-97`, `D-103`).

Phase 2's done-when, asserted end to end: *a token issues, is used, shows
`last_used_at`, revokes, and 401s on the next call; and a teacher cannot issue a
token exceeding her own authority.*

The tests that matter most are the negative ones. A credential system is only as
good as what it refuses, and three refusals here are load-bearing:

- a **teacher cannot grant herself `fees`** through a connector (the fee fence,
  now on the credential path as well as the schema path);
- a **JWT is not a connector token and a connector token is not a JWT** — two
  doors, neither accepting the other's key;
- **switching `agent_access` to `off` kills tokens already issued**, not just
  new ones. A kill switch that only stops future connections is not a switch.
"""

import uuid

import pytest

# --- helpers -----------------------------------------------------------------


def _org(client, cleanup, *, agent_access="admins"):
    """A fresh school with an admin, and agent access configured."""
    email = f"admin-{uuid.uuid4().hex[:12]}@example.com"
    reg = client.post("/api/v1/auth/register-org",
                      json={"org_name": "Connector Org", "name": "Director",
                            "email": email, "password": "supersecret1",
                            "timezone": "Asia/Kolkata"}).json()
    cleanup["orgs"].append(uuid.UUID(reg["org"]["id"]))
    cleanup["users"].append(uuid.UUID(reg["user"]["id"]))
    h = {"Authorization": f"Bearer {reg['access_token']}"}
    if agent_access is not None:
        r = client.patch("/api/v1/org/settings", headers=h,
                         json={"agent_access": agent_access})
        assert r.status_code == 200, r.text
    return h, reg


def _teacher(client, admin_h):
    bulk = client.post("/api/v1/org/members/bulk", headers=admin_h, json={"members": [
        {"username": f"t{uuid.uuid4().hex[:8]}", "password": "supersecret1",
         "role": "teacher"}]})
    cred = bulk.json()["results"][0]
    login = client.post("/api/v1/auth/login",
                        json={"identifier": cred["username"],
                              "password": "supersecret1"}).json()
    return {"Authorization": f"Bearer {login['access_token']}"}


def _issue(client, h, **kw):
    body = {"name": "Claude Desktop", "scopes": ["students"], "mode": "read"}
    body.update(kw)
    return client.post("/api/v1/org/api-tokens", headers=h, json=body)


# --- the default, and the gate ------------------------------------------------

def test_a_new_school_cannot_issue_a_connector_at_all(client, cleanup):
    """`D-103`: `off` is the default. A school still being set up has nothing to
    connect an agent to, and the safe default is the one nobody has to choose."""
    h, _ = _org(client, cleanup, agent_access=None)
    settings = client.get("/api/v1/org/settings", headers=h).json()
    assert settings["agent_access"] == "off"

    r = _issue(client, h)
    assert r.status_code == 403, r.text
    assert "switched off" in r.json()["error"]["message"]


def test_admins_only_means_a_teacher_cannot_issue_one(client, cleanup):
    admin_h, _ = _org(client, cleanup, agent_access="admins")
    teacher_h = _teacher(client, admin_h)
    r = _issue(client, teacher_h)
    assert r.status_code == 403
    assert "Only admins" in r.json()["error"]["message"]

    # ...and the same teacher may, once the school opens it up.
    client.patch("/api/v1/org/settings", headers=admin_h,
                 json={"agent_access": "all_staff"})
    assert _issue(client, teacher_h).status_code == 201


# --- issue -> use -> revoke -> 401 (the Phase 2 done-when) --------------------

def test_a_token_issues_is_used_shows_last_used_then_revokes(client, cleanup):
    h, reg = _org(client, cleanup)
    created = _issue(client, h, scopes=["students", "attendance"]).json()

    secret = created["secret"]
    assert secret.startswith(("tbk_live_", "tbk_test_"))
    assert created["token"]["prefix"] == secret[:12]
    assert created["token"]["last_used_at"] is None
    # `core` is folded in server-side — a scope you cannot navigate out of is
    # not a scope.
    assert "core" in created["token"]["scopes"]

    agent_h = {"Authorization": f"Bearer {secret}"}
    me = client.get("/api/v1/agent/me", headers=agent_h)
    assert me.status_code == 200, me.text
    body = me.json()
    assert body["org_id"] == reg["org"]["id"]
    assert body["mode"] == "read"
    assert body["tools"] > 0
    assert set(body["domains"]) <= set(body["scopes"])

    listed = client.get("/api/v1/org/api-tokens", headers=h).json()
    assert len(listed) == 1
    assert listed[0]["last_used_at"] is not None, "using a token must record it"
    # The secret is shown exactly once and is not recoverable from anywhere.
    assert "secret" not in listed[0]
    assert secret not in str(listed[0])

    revoked = client.delete(f"/api/v1/org/api-tokens/{created['token']['id']}",
                            headers=h)
    assert revoked.status_code == 200
    assert revoked.json()["revoked_at"] is not None

    dead = client.get("/api/v1/agent/me", headers=agent_h)
    assert dead.status_code == 401, "a revoked token must fail on the next call"


def test_switching_agent_access_off_kills_a_live_token(client, cleanup):
    """A kill switch that only stops *new* connections is not a kill switch."""
    h, _ = _org(client, cleanup)
    secret = _issue(client, h).json()["secret"]
    agent_h = {"Authorization": f"Bearer {secret}"}
    assert client.get("/api/v1/agent/me", headers=agent_h).status_code == 200

    client.patch("/api/v1/org/settings", headers=h, json={"agent_access": "off"})
    assert client.get("/api/v1/agent/me", headers=agent_h).status_code == 401


# --- a connector never exceeds its issuer -------------------------------------

def test_a_teacher_cannot_grant_herself_fees_or_insights(client, cleanup):
    """The fee fence on the credential path. A teacher asking for `fees` is
    refused outright rather than handed a connector that silently holds nothing
    — being told something false about your own credential is worse."""
    admin_h, _ = _org(client, cleanup, agent_access="all_staff")
    teacher_h = _teacher(client, admin_h)

    for domain in ("fees", "insights"):
        r = _issue(client, teacher_h, scopes=[domain])
        assert r.status_code == 403, f"{domain}: {r.text}"
        assert "never exceeds" in r.json()["error"]["message"]

    # The admin who *can* do it herself may grant it.
    assert _issue(client, admin_h, scopes=["fees"]).status_code == 201


def test_a_teachers_connector_resolves_to_no_fee_tool(client, cleanup):
    """Belt and braces: even with every toolset she can legitimately hold, a
    teacher's connector must not resolve a single fee tool."""
    admin_h, _ = _org(client, cleanup, agent_access="all_staff")
    teacher_h = _teacher(client, admin_h)
    secret = _issue(client, teacher_h,
                    scopes=["students", "attendance", "capture", "planning",
                            "exams", "tasks"]).json()["secret"]
    body = client.get("/api/v1/agent/me",
                      headers={"Authorization": f"Bearer {secret}"}).json()
    assert "fees" not in body["domains"]
    assert "insights" not in body["domains"]


def test_unknown_toolsets_are_refused(client, cleanup):
    h, _ = _org(client, cleanup)
    r = _issue(client, h, scopes=["payroll"])
    assert r.status_code == 422
    assert "payroll" in r.json()["error"]["message"]


# --- two doors, neither accepting the other's key -----------------------------

def test_a_jwt_is_not_a_connector_token(client, cleanup):
    h, _ = _org(client, cleanup)
    r = client.get("/api/v1/agent/me", headers=h)
    assert r.status_code == 401, "a browser session must not drive the agent door"


def test_a_connector_token_is_not_a_session(client, cleanup):
    h, _ = _org(client, cleanup)
    secret = _issue(client, h).json()["secret"]
    agent_h = {"Authorization": f"Bearer {secret}"}
    assert client.get("/api/v1/org/settings", headers=agent_h).status_code == 401
    assert client.get("/api/v1/org/api-tokens", headers=agent_h).status_code == 401


@pytest.mark.parametrize("bogus", ["nonsense", "tbk_live_notarealtoken"])
def test_a_bad_token_is_refused_without_saying_why(client, bogus):
    r = client.get("/api/v1/agent/me",
                   headers={"Authorization": f"Bearer {bogus}"})
    assert r.status_code == 401
    # Never distinguishes revoked / expired / never-existed.
    assert "Invalid API token" in r.text


# --- scoping between schools --------------------------------------------------

def test_a_token_lists_and_revokes_only_within_its_own_school(client, cleanup):
    """Law 1: org_id comes from the credential, never from the request."""
    h_a, _ = _org(client, cleanup)
    h_b, _ = _org(client, cleanup)
    token_a = _issue(client, h_a).json()["token"]

    assert client.get("/api/v1/org/api-tokens", headers=h_b).json() == []
    r = client.delete(f"/api/v1/org/api-tokens/{token_a['id']}", headers=h_b)
    assert r.status_code == 404, "another school's connector is not even visible"


def test_a_teacher_sees_only_her_own_connectors(client, cleanup):
    admin_h, _ = _org(client, cleanup, agent_access="all_staff")
    teacher_h = _teacher(client, admin_h)
    _issue(client, admin_h, name="Director's laptop")
    mine = _issue(client, teacher_h, name="My laptop").json()["token"]

    teacher_list = client.get("/api/v1/org/api-tokens", headers=teacher_h).json()
    assert [t["id"] for t in teacher_list] == [mine["id"]]
    admin_list = client.get("/api/v1/org/api-tokens", headers=admin_h).json()
    assert len(admin_list) == 2


def test_a_teacher_cannot_revoke_someone_elses_connector(client, cleanup):
    admin_h, _ = _org(client, cleanup, agent_access="all_staff")
    teacher_h = _teacher(client, admin_h)
    theirs = _issue(client, admin_h, name="Director's laptop").json()["token"]
    r = client.delete(f"/api/v1/org/api-tokens/{theirs['id']}", headers=teacher_h)
    assert r.status_code == 403


# --- expiry -------------------------------------------------------------------

def test_expiry_is_offered_as_fixed_choices(client, cleanup):
    h, _ = _org(client, cleanup)
    assert _issue(client, h, expires_days=90).status_code == 201
    assert _issue(client, h, expires_days=7).status_code == 422
    # Omitted = never expires, which is a real choice the screen offers.
    assert _issue(client, h).json()["token"]["expires_at"] is None
