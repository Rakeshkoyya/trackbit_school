"""The post-setup edit gaps closed on 2026-08-10 — the ones that needed a route
or a service change, not just a screen.

Each test names the failure it prevents rather than the function it calls:

  * a school that answered "No" to the parent portal on its setup pack could not
    be switched on afterwards at all. The column was written once by the pack
    committer, was absent from `OrgSettingsUpdate`, and had no endpoint — while
    `readiness.py` reported the school as not-ready and offered nothing to act on.
  * a holiday with a misspelt name or a date typed one day out could only be
    deleted and repainted, on a row the planner had already paced around.
  * a school's own term names were silently rewritten to "Term 1"/"Term 2" by
    `sync_terms_from_exams` the next time anybody touched an exam block — which
    would have made the new rename control revert under the user.
"""

import uuid
from datetime import date, timedelta

from app.models import Organization
from tests.conftest import AdminSession


def _org(client, cleanup) -> tuple[dict, dict, uuid.UUID]:
    """An admin, their org, and an active year — the minimum these routes need."""
    email = f"admin-{uuid.uuid4().hex[:12]}@example.com"
    reg = client.post("/api/v1/auth/register-org", json={
        "org_name": "Gaps Org", "name": "Director", "email": email,
        "password": "supersecret1", "timezone": "Asia/Kolkata"}).json()
    cleanup["orgs"].append(uuid.UUID(reg["org"]["id"]))
    cleanup["users"].append(uuid.UUID(reg["user"]["id"]))
    headers = {"Authorization": f"Bearer {reg['access_token']}"}

    today = date.today()
    year = client.post("/api/v1/academics/years", headers=headers, json={
        "label": "2026-27",
        "start_date": (today - timedelta(days=60)).isoformat(),
        "end_date": (today + timedelta(days=200)).isoformat()}).json()
    return headers, year, uuid.UUID(reg["org"]["id"])


# ── the parent portal switch ─────────────────────────────────────────────────
def test_the_parent_portal_can_be_switched_after_the_pack_is_imported(client, cleanup):
    h, _year, org_id = _org(client, cleanup)
    assert client.get("/api/v1/org/settings", headers=h).json()["parent_portal_enabled"]

    off = client.patch("/api/v1/org/settings", headers=h,
                       json={"parent_portal_enabled": False})
    assert off.status_code == 200, off.text
    assert off.json()["parent_portal_enabled"] is False

    # The guard every parent request runs reads the column, not the response, so
    # assert against the row itself.
    db = AdminSession()
    try:
        assert db.get(Organization, org_id).parent_portal_enabled is False
    finally:
        db.close()

    on = client.patch("/api/v1/org/settings", headers=h,
                      json={"parent_portal_enabled": True})
    assert on.json()["parent_portal_enabled"] is True


def test_switching_the_portal_off_does_not_disturb_the_rest_of_the_form(client, cleanup):
    """`False` is a value, not an absence. A settings loop that tested truthiness
    instead of `is not None` would drop it and leave the portal quietly open."""
    h, _year, _ = _org(client, cleanup)
    client.patch("/api/v1/org/settings", headers=h, json={"board": "CBSE"})

    res = client.patch("/api/v1/org/settings", headers=h,
                       json={"parent_portal_enabled": False}).json()
    assert res["parent_portal_enabled"] is False
    assert res["board"] == "CBSE"


# ── correcting a day already on the calendar ─────────────────────────────────
def test_a_holiday_can_be_corrected_in_place(client, cleanup):
    h, year, _ = _org(client, cleanup)
    day = (date.today() + timedelta(days=10)).isoformat()
    event = client.post("/api/v1/academics/calendar/events", headers=h, json={
        "academic_year_id": year["id"], "type": "holiday",
        "title": "Foundrs Day", "start_date": day, "end_date": day}).json()

    moved = (date.today() + timedelta(days=12)).isoformat()
    res = client.patch(f"/api/v1/academics/calendar/events/{event['id']}", headers=h,
                       json={"title": "Founder's Day", "start_date": moved,
                             "end_date": moved})

    assert res.status_code == 200, res.text
    assert res.json()["title"] == "Founder's Day"
    assert res.json()["start_date"] == moved
    assert res.json()["end_date"] == moved


def test_an_end_date_before_the_start_is_refused(client, cleanup):
    """Either date may arrive alone, so the order can only be judged after
    merging with the stored row — which is why the schema cannot catch this."""
    h, year, _ = _org(client, cleanup)
    event = client.post("/api/v1/academics/calendar/events", headers=h, json={
        "academic_year_id": year["id"], "type": "holiday",
        "title": "Sports Week",
        "start_date": (date.today() + timedelta(days=10)).isoformat(),
        "end_date": (date.today() + timedelta(days=14)).isoformat()}).json()

    res = client.patch(f"/api/v1/academics/calendar/events/{event['id']}", headers=h,
                       json={"end_date": (date.today() + timedelta(days=3)).isoformat()})

    assert res.status_code >= 400
    assert res.json()["error"]["code"] == "bad_date_order"


# ── the term name is the school's, the window is the exam's ──────────────────
def test_a_schools_own_term_name_survives_an_exam_being_moved(client, cleanup):
    """Terms derive their WINDOW from the exam that closes them (founder,
    2026-08-08). Their NAME does not, and used to be overwritten on every sync —
    so renaming a term would have reverted the moment anyone touched an exam."""
    h, year, _ = _org(client, cleanup)

    def exam_block(title: str, start: int, end: int) -> dict:
        return client.post("/api/v1/academics/calendar/events", headers=h, json={
            "academic_year_id": year["id"], "type": "exam_block", "title": title,
            "start_date": (date.today() + timedelta(days=start)).isoformat(),
            "end_date": (date.today() + timedelta(days=end)).isoformat()}).json()

    # Two exams, so the term under test is NOT the last one — the last is
    # deliberately stretched to the year's end, which would hide the window move.
    half_yearly = exam_block("Half-yearly", 30, 34)
    exam_block("Annual", 120, 124)

    terms = client.get(f"/api/v1/academics/terms?year_id={year['id']}", headers=h).json()
    assert len(terms) == 2, "each exam block should close a term"
    renamed = client.patch(f"/api/v1/academics/terms/{terms[0]['id']}", headers=h,
                           json={"name": "First Term"})
    assert renamed.status_code == 200, renamed.text

    moved = (date.today() + timedelta(days=36)).isoformat()
    client.patch(f"/api/v1/academics/calendar/events/{half_yearly['id']}", headers=h,
                 json={"end_date": moved})

    after = client.get(f"/api/v1/academics/terms?year_id={year['id']}", headers=h).json()
    assert after[0]["name"] == "First Term", "the sync overwrote the school's name"
    assert after[0]["end_date"] == moved, "but the window still follows the exam"


# ── the rest of what the setup screens can now correct ───────────────────────
def test_a_year_and_a_class_can_both_be_renamed(client, cleanup):
    """Both PATCH routes have existed since P0-C with no screen wired to them, so
    a typo could only be fixed by deleting the row — which takes its chapters,
    students, plans and timetable with it."""
    h, year, _ = _org(client, cleanup)

    relabelled = client.patch(f"/api/v1/academics/years/{year['id']}", headers=h,
                              json={"label": "2026-2027"})
    assert relabelled.status_code == 200, relabelled.text
    assert relabelled.json()["label"] == "2026-2027"

    klass = client.post("/api/v1/academics/classes", headers=h, json={
        "academic_year_id": year["id"], "name": "6", "section": "A"}).json()
    renamed = client.patch(f"/api/v1/academics/classes/{klass['id']}", headers=h,
                           json={"name": "VI", "section": "B"})
    assert renamed.status_code == 200, renamed.text
    assert (renamed.json()["name"], renamed.json()["section"]) == ("VI", "B")


def test_a_year_cannot_be_inverted_now_that_its_dates_are_editable(client, cleanup):
    """Making the window editable made this reachable. An inverted year is not
    cosmetic: `teaching_days` counts nothing, the term sync walks its cursor from
    a start past every exam, and every forecast divides by a window that is not
    there. Either date can arrive alone, so the schema cannot catch it."""
    h, year, _ = _org(client, cleanup)

    res = client.patch(f"/api/v1/academics/years/{year['id']}", headers=h,
                       json={"end_date": (date.today() - timedelta(days=200)).isoformat()})

    assert res.status_code >= 400
    assert res.json()["error"]["code"] == "bad_date_order"
    # and the stored window is untouched
    unchanged = client.get("/api/v1/academics/years", headers=h).json()
    assert unchanged[0]["end_date"] == year["end_date"]
