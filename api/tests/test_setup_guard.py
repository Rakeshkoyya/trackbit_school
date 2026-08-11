"""P6 — what a school may change after we hand it over (SETUP-REDESIGN-PLAN §6).

The founder's rule, verbatim: *"there will be no setup screen or anything like
that for the school admin once we handed over; only we super admin can edit to
change the data."* So handover is the gate, not the role — before it the school
is being built, after it the school is live.

What each test is defending:

  * **structure freezes at handover.** A live school with teachers logging
    against its plan cannot have a class deleted or a subject renamed by
    somebody clicking around;
  * **people and daily work never freeze** (D-1). The school admits students in
    June, August and January, hires and loses staff, declares an unexpected
    holiday and collects fees — every one of those still works after handover.
    A setup freeze that stopped admissions would put a support ticket between a
    school and enrolling a child;
  * **and neither does the syllabus** (SY-2). A chapter added in September is a
    teaching record, not the school's shape. It used to be frozen with the
    structure, which left the Syllabus grid offering an "Add chapter" button
    every live school would be refused. What guards it now is the narrower
    *is this subject yours*, asked in the service rather than on the route;
  * **the operator is never blocked**, in any school, at any time;
  * **the frozen list is exactly what we think it is.** The last test pins it,
    so a route added to the wrong guard fails here rather than in a school.
"""

import uuid
from datetime import UTC, datetime

import pytest

from app.models import Organization, User
from tests.conftest import AdminSession

# Frozen at handover: the school's shape. Everything here is set up by us.
STRUCTURE = [
    ("post", "/api/v1/academics/years", {"label": "2027-28",
                                         "start_date": "2027-06-01",
                                         "end_date": "2028-04-30"}),
    ("post", "/api/v1/academics/subjects", {"name": "Sanskrit"}),
]


def _register(client, cleanup, org_name="Guard School"):
    email = f"a-{uuid.uuid4().hex[:12]}@example.com"
    reg = client.post("/api/v1/auth/register-org", json={
        "org_name": org_name, "name": "School Admin", "email": email,
        "password": "supersecret1", "timezone": "Asia/Kolkata"}).json()
    cleanup["orgs"].append(uuid.UUID(reg["org"]["id"]))
    cleanup["users"].append(uuid.UUID(reg["user"]["id"]))
    return reg


def _headers(reg):
    return {"Authorization": f"Bearer {reg['access_token']}"}


def _hand_over(org_id: str) -> None:
    """Stamp handover directly: no route exposes it to a non-super user, which
    is the point."""
    db = AdminSession()
    try:
        org = db.get(Organization, uuid.UUID(org_id))
        org.handed_over_at = datetime.now(UTC)
        db.commit()
    finally:
        db.close()


def _make_super(user_id: str) -> None:
    db = AdminSession()
    try:
        db.get(User, uuid.UUID(user_id)).is_super_admin = True
        db.commit()
    finally:
        db.close()


@pytest.fixture
def live_school(client, cleanup):
    """A handed-over school and its own admin — the state a real school is in.

    The year is created BEFORE handover, which is both what actually happens and
    what makes the school realistic: a live school always has one, and several
    operational routes hang off it.
    """
    reg = _register(client, cleanup)
    client.post("/api/v1/academics/years",
                json={"label": "2026-27", "start_date": "2026-06-01",
                      "end_date": "2027-04-30"}, headers=_headers(reg))
    _hand_over(reg["org"]["id"])
    return reg


# ── before handover, the school is still being built ─────────────────────────
def test_before_handover_the_school_can_still_be_built(client, cleanup):
    reg = _register(client, cleanup)
    r = client.post("/api/v1/academics/subjects", json={"name": "Mathematics"},
                    headers=_headers(reg))
    assert r.status_code == 200


# ── after handover, structure freezes ────────────────────────────────────────
@pytest.mark.parametrize("method,path,body", STRUCTURE)
def test_structure_freezes_at_handover(live_school, client, method, path, body):
    r = getattr(client, method)(path, json=body, headers=_headers(live_school))
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "operator_only"
    # The message tells the school what to do, not what it lacks.
    assert "TrackBit" in r.json()["error"]["message"]


def test_the_timetable_freezes_at_handover(live_school, client):
    r = client.put("/api/v1/timetable/period-config",
                   json={"academic_year_id": str(uuid.uuid4()),
                         "periods_per_day": 8, "period_times": []},
                   headers=_headers(live_school))
    assert r.status_code == 403


def test_the_syllabus_does_NOT_freeze_at_handover(live_school, client):
    """SY-2 narrows `D-1` for the syllabus, deliberately.

    The syllabus used to be `require_operator`, so a handed-over school could
    not add a chapter — and the founder's grid offers exactly that control on
    every subject. That was the wrong reading of the freeze: a class, a subject
    and who teaches it are the school's SHAPE and still freeze (the tests above
    pin them). A chapter added in September is a live teaching record, like an
    admission or a holiday, and `D-1` never meant to stop those.

    What replaces the freeze is the narrower question — *is this subject
    yours* — asked in the SERVICE, so it holds for in-process callers too. This
    test pins both halves: a real subject goes through, a foreign id does not.
    """
    year = client.get("/api/v1/academics/years",
                      headers=_headers(live_school)).json()[0]
    # Structure is frozen after handover, so build the class-subject the way it
    # really would be — as the operator.
    _make_super(live_school["user"]["id"])
    sub = client.post("/api/v1/academics/subjects", json={"name": "Civics"},
                      headers=_headers(live_school)).json()
    klass = client.post("/api/v1/academics/classes",
                        json={"academic_year_id": year["id"], "name": "9",
                              "section": "A"},
                        headers=_headers(live_school)).json()
    cs = client.post("/api/v1/academics/class-subjects",
                     json={"class_id": klass["id"], "subject_id": sub["id"],
                           "periods_per_week": 4},
                     headers=_headers(live_school)).json()

    r = client.post("/api/v1/planner/syllabus/units",
                    json={"class_subject_id": cs["id"], "title": "New chapter"},
                    headers=_headers(live_school))
    assert r.status_code == 200, r.text

    # A class-subject that is not this org's is still refused — the guard moved,
    # it did not disappear.
    r = client.post("/api/v1/planner/syllabus/units",
                    json={"class_subject_id": str(uuid.uuid4()), "title": "Nope"},
                    headers=_headers(live_school))
    assert r.status_code == 404, r.text


def test_plan_approval_freezes_at_handover(live_school, client):
    r = client.post(f"/api/v1/planner/plan/{uuid.uuid4()}/approve",
                    headers=_headers(live_school))
    assert r.status_code == 403


# ── people and daily work never freeze (D-1) ─────────────────────────────────
def test_a_handed_over_school_can_still_admit_a_student(live_school, client):
    """June, August and January. A freeze that stopped this would put a support
    ticket between a school and enrolling a child."""
    r = client.post("/api/v1/students",
                    json={"admission_no": f"A{uuid.uuid4().hex[:6]}",
                          "full_name": "Aarav Sharma"},
                    headers=_headers(live_school))
    assert r.status_code == 200, r.text


def test_a_handed_over_school_can_still_add_staff(live_school, client):
    r = client.post("/api/v1/org/members/invite",
                    json={"email": f"t-{uuid.uuid4().hex[:8]}@example.com",
                          "name": "New Teacher", "org_role": "teacher"},
                    headers=_headers(live_school))
    assert r.status_code in (200, 201), r.text


def test_a_handed_over_school_can_still_declare_a_holiday(live_school, client):
    """An unexpected closure is operational. Nobody is calling us at 7am to add
    a holiday."""
    years = client.get("/api/v1/academics/years",
                       headers=_headers(live_school)).json()
    assert years, "the fixture creates a year before handover"
    r = client.post("/api/v1/academics/calendar/events",
                    json={"academic_year_id": years[0]["id"], "type": "holiday",
                          "title": "Sudden closure", "start_date": "2026-09-01",
                          "end_date": "2026-09-01", "affects_teaching": True},
                    headers=_headers(live_school))
    assert r.status_code == 200, r.text


def test_a_handed_over_school_can_still_read_its_own_structure(live_school, client):
    """D-2: the admin sees everything. Only the write affordance goes."""
    h = _headers(live_school)
    for path in ("/api/v1/academics/classes", "/api/v1/academics/subjects",
                 "/api/v1/academics/years"):
        assert client.get(path, headers=h).status_code == 200


# ── the operator is never blocked ────────────────────────────────────────────
def test_the_operator_can_change_structure_in_a_handed_over_school(
        client, cleanup):
    school = _register(client, cleanup, "Operator Target")
    _hand_over(school["org"]["id"])

    operator = _register(client, cleanup, "Operator Home")
    _make_super(operator["user"]["id"])
    session = client.post(
        f"/api/v1/platform/orgs/{school['org']['id']}/enter",
        headers=_headers(operator)).json()

    r = client.post("/api/v1/academics/subjects", json={"name": "Sanskrit"},
                    headers={"Authorization": f"Bearer {session['access_token']}"})
    assert r.status_code == 200, r.text


# ── the frozen list is exactly what we think it is ───────────────────────────
def test_the_operator_only_surface_is_the_one_we_meant():
    """Pins the split. A structure route added under `require_admin`, or an
    operational one moved under `require_operator` by accident, fails here
    rather than in a school."""
    from app.main import app

    frozen: set[str] = set()
    for route in app.routes:
        for dep in getattr(getattr(route, "dependant", None), "dependencies", []):
            if getattr(dep.call, "__name__", "") == "require_operator":
                frozen.add(f"{sorted(route.methods)[0]} {route.path}")

    prefixes = (
        "/api/v1/academics/years", "/api/v1/academics/terms",
        "/api/v1/academics/subjects", "/api/v1/academics/classes",
        "/api/v1/academics/class-subjects", "/api/v1/planner/syllabus",
        "/api/v1/planner/plan/", "/api/v1/timetable/",
    )
    for entry in frozen:
        path = entry.split(" ", 1)[1]
        assert path.startswith(prefixes), (
            f"{entry} is frozen but is not school structure")

    # The things a live school must keep. If any of these ever appears above,
    # a school has lost the ability to run its own day.
    for entry in ("POST /api/v1/students",
                  "POST /api/v1/org/members/invite",
                  "POST /api/v1/academics/calendar/events",
                  "PATCH /api/v1/planner/syllabus/chapters/{unit_id}"):
        assert entry not in frozen, f"{entry} must not freeze at handover"
    assert len(frozen) >= 30, "the structure surface should not have shrunk"
