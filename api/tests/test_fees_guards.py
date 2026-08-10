"""FE-1f — the fee fence, asserted route by route.

*"Teachers never see fees"* is one of the two hard rules that hold on every
surface. FE-1 added fourteen routes to this module, and a guard is exactly the
kind of thing that gets forgotten on the fifteenth — so this walks the router
itself rather than a hand-written list, and fails when a new fee route appears
without a teacher being refused.

The single permitted door is `D-83`: a teacher **assigned** a fee follow-up task
may read that one student's fee detail inside that one task. That is
`/fees/followup/{task_id}`, and the service enforces the assignment.
"""

import uuid
from pathlib import Path

import pytest

from app.main import app

# `D-83`'s one exception, and the only path in this module a teacher may reach.
_TEACHER_MAY_REACH = {"/api/v1/fees/followup/{task_id}"}


def _fee_routes():
    out = []
    for route in app.routes:
        path = getattr(route, "path", "")
        if not path.startswith("/api/v1/fees"):
            continue
        for method in sorted(getattr(route, "methods", set()) - {"HEAD", "OPTIONS"}):
            out.append((method, path))
    return sorted(out)


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture
def teacher(client, cleanup):
    """An admin's school, and a teacher inside it."""
    email = f"admin-{uuid.uuid4().hex[:12]}@example.com"
    reg = client.post("/api/v1/auth/register-org",
                      json={"org_name": "Fence Org", "name": "Director",
                            "email": email, "password": "supersecret1",
                            "timezone": "Asia/Kolkata"}).json()
    cleanup["orgs"].append(uuid.UUID(reg["org"]["id"]))
    cleanup["users"].append(uuid.UUID(reg["user"]["id"]))
    admin_h = _h(reg["access_token"])

    invite = client.post("/api/v1/org/members/invite", headers=admin_h,
                         json={"name": "Teacher", "phone": "+919800004321",
                               "role": "teacher"})
    assert invite.status_code == 200, invite.text
    data = invite.json()
    cleanup["users"].append(uuid.UUID(data["user_id"]))
    token = data["invite_url"].rsplit("/join/", 1)[1]

    session = client.post("/api/v1/auth/verify", json={"token": token})
    assert session.status_code == 200, session.text
    assert session.json()["org_role"] == "teacher"
    return _h(session.json()["access_token"])


def test_there_are_fee_routes_to_guard():
    """Guards against the test silently passing because it found nothing."""
    assert len(_fee_routes()) >= 30


def test_a_teacher_is_refused_on_every_fee_route(client, teacher):
    """Walks the router, so a route added later without a guard fails here.

    A 404 counts as refused: several routes resolve an id first, and a teacher
    who cannot see the record gets "not found" rather than "forbidden". What is
    NOT acceptable is a 2xx — that is a teacher reading a family's money.
    """
    leaked = []
    for method, path in _fee_routes():
        if path in _TEACHER_MAY_REACH:
            continue
        # Any well-formed id: the guard must bite before the lookup does.
        url = (path.replace("{fs_id}", str(uuid.uuid4()))
                   .replace("{sf_id}", str(uuid.uuid4()))
                   .replace("{inst_id}", str(uuid.uuid4()))
                   .replace("{txn_id}", str(uuid.uuid4()))
                   .replace("{proof_id}", str(uuid.uuid4()))
                   .replace("{task_id}", str(uuid.uuid4())))
        response = client.request(method, url, headers=teacher, json={})
        if response.status_code < 400:
            leaked.append(f"{method} {path} -> {response.status_code}")
    assert not leaked, "teachers reached fee routes: " + "; ".join(leaked)


def test_the_one_permitted_door_is_still_only_a_door(client, teacher):
    """`D-83`: a teacher may reach `followup/{task_id}`, but only for a task
    actually assigned to her. An arbitrary id must not open it."""
    r = client.get(f"/api/v1/fees/followup/{uuid.uuid4()}", headers=teacher)
    assert r.status_code >= 400, r.text


def test_no_fee_route_still_uses_the_retired_alias():
    """`D-126`: `require_office_up` is an admin-only alias CLAUDE.md asks to
    consolidate on touch. FE-1 touched every route in this module."""
    source = Path("app/api/v1/endpoints/fees.py").read_text(encoding="utf-8")
    # The module docstring explains the retirement, so match on USE, not on the
    # word — the first version of this test failed on its own explanation.
    assert "Depends(require_office_up)" not in source
    assert "import require_office_up" not in source
    assert ", require_office_up" not in source
