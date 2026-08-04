"""V1-20 — the annual xlsx import and the school-side catalogue browse.

What each test is defending:

  * **Day-first dates.** This is an Indian product reading Indian state
    notifications: `03/04/2028` is 3 April. `%m/%d/%Y` is deliberately absent
    from the parser, because silently accepting it turns 3 April into 4 March on
    exactly the rows where both readings parse — a calendar's worst failure, and
    a completely silent one.

  * **Broken rows are reported, never dropped.** An importer that discards what
    it cannot read announces "142 imported" over a file of 150 and nobody ever
    finds the eight. Each missing row here is a day a school stays open for.

  * **A duplicate (key, date) inside one file is caught.** `bulk()` upserts, so
    the second row would silently overwrite the first — the same shape as the
    defect V1-19 existed to fix, this time arriving from a spreadsheet.

  * **The model maps columns; it never decides a date** (`ingest.py`, `S-123`).
    The suite runs with AI off, and the heuristic alone must place a plainly
    named sheet — otherwise onboarding is untestable offline.

  * **Absent state ≠ "all states" in the browse.** The dropdown shows the
    school's own state before anyone touches it, so omitting the param must
    filter to that state. Collapsing the two renders "Kerala" over a table of
    every state in the country.

  * **The browse is admin-only** (`D-57` — everything that leads to a decision),
    and it never leaks platform telemetry: a school sees what IT decided, never
    `decided_count` across other schools.
"""

import io
import uuid
from datetime import date, timedelta

import pytest
from openpyxl import Workbook

from app.models import User
from app.services import observance_import as oi
from tests.conftest import AdminSession


def _make_super(user_id: str) -> None:
    db = AdminSession()
    try:
        db.get(User, uuid.UUID(user_id)).is_super_admin = True
        db.commit()
    finally:
        db.close()


def _org(client, cleanup, *, state: str | None = "Kerala"):
    email = f"admin-{uuid.uuid4().hex[:12]}@example.com"
    reg = client.post("/api/v1/auth/register-org", json={
        "org_name": "Import Org", "name": "Director", "email": email,
        "password": "supersecret1", "timezone": "Asia/Kolkata"}).json()
    cleanup["orgs"].append(uuid.UUID(reg["org"]["id"]))
    cleanup["users"].append(uuid.UUID(reg["user"]["id"]))
    h = {"Authorization": f"Bearer {reg['access_token']}"}
    if state:
        client.patch("/api/v1/org/settings", headers=h, json={"state": state})
    today = date.today()
    client.post("/api/v1/academics/years", headers=h, json={
        "label": "2026-27", "start_date": (today - timedelta(days=30)).isoformat(),
        "end_date": (today + timedelta(days=300)).isoformat()})
    return {"h": h, "org_id": reg["org"]["id"], "user_id": reg["user"]["id"]}


def _sheet(rows, header=("Festival Name", "Date", "Last Day", "Applicable States",
                         "Type", "Importance", "Notes")) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append(list(header))
    for r in rows:
        ws.append(list(r))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ── the parser ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    ("2028-10-17", date(2028, 10, 17)),
    ("17/10/2028", date(2028, 10, 17)),
    ("17-10-2028", date(2028, 10, 17)),
    ("17 Oct 2028", date(2028, 10, 17)),
    ("17 October 2028", date(2028, 10, 17)),
    ("17-Oct-2028", date(2028, 10, 17)),
    ("15th August 2028", date(2028, 8, 15)),
    ("Oct 17 2028", date(2028, 10, 17)),
])
def test_date_parser_reads_the_formats_state_notifications_use(raw, expected):
    assert oi._parse_date(raw) == expected


def test_dates_are_read_day_first():
    """`03/04/2028` is 3 April in every source this importer consumes. The
    American reading is not a fallback — it is absent, because a parser that
    tries both silently relabels a third of the year."""
    assert oi._parse_date("03/04/2028") == date(2028, 4, 3)
    assert oi._parse_date("04/03/2028") == date(2028, 3, 4)
    # Unreadable stays unreadable; it never becomes a guess.
    assert oi._parse_date("next Tuesday") is None
    assert oi._parse_date("") is None


def test_states_cell_resolves_and_reports_what_it_cannot_place():
    assert oi._parse_states("Kerala; Lakshadweep")[0] == ["Kerala", "Lakshadweep"]
    assert oi._parse_states("TN, Pondicherry")[0] == ["Tamil Nadu", "Puducherry"]
    # The commonest thing this column says is "everywhere", in several words.
    for word in ("", "All India", "national", "-", "N/A"):
        assert oi._parse_states(word) == (None, [])
    resolved, bad = oi._parse_states("Kerala, Atlantis")
    assert resolved == ["Kerala"] and bad == ["Atlantis"]


def test_preview_keeps_broken_rows_and_says_why():
    data = _sheet([
        ("Diwali", "2028-10-17", None, "All India", "Public Holiday", "High", None),
        ("Onam", "03/09/2028", "06/09/2028", "Kerala; Lakshadweep", "holiday", "major", None),
        ("Broken", "not a date", None, "Kerala", "holiday", "major", None),
        (None, "2028-06-01", None, "Bihar", "holiday", "major", None),
        ("Bad state", "2028-05-01", None, "Atlantis", "festival", "minor", None),
    ])
    analysis = oi.analyze(data)
    # AI is off in the suite: the heuristic alone must place a plainly named
    # sheet, or setup cannot be tested offline (`ingest.py`).
    assert analysis["source"] == "heuristic"
    assert analysis["mapping"]["name"] == "Festival Name"
    assert analysis["mapping"]["date"] == "Date"
    assert analysis["missing_required"] == []

    rows = oi.preview(mapping=analysis["mapping"], rows=analysis["rows"],
                      default_source="Test sheet")
    assert len(rows) == 5, "every row comes back, including the broken ones"
    by_name = {r.name: r for r in rows}

    assert by_name["Diwali"].importable and by_name["Diwali"].states is None
    assert by_name["Diwali"].kind == "holiday"      # "Public Holiday" alias
    assert by_name["Diwali"].tier == "major"        # "High" alias

    onam = by_name["Onam"]
    assert onam.date == date(2028, 9, 3) and onam.end_date == date(2028, 9, 6)
    assert onam.states == ["Kerala", "Lakshadweep"]

    assert not by_name["Broken"].importable
    assert any("not a date" in p for p in by_name["Broken"].problems)
    assert not by_name["Bad state"].importable
    assert any("Atlantis" in p for p in by_name["Bad state"].problems)
    assert sum(1 for r in rows if not r.importable) == 3   # + the unnamed row


# ── end to end, through the endpoints ────────────────────────────────────────

def test_import_is_super_admin_only(client, cleanup):
    ctx = _org(client, cleanup)
    data = _sheet([("Diwali", "2028-10-17", None, "All India", "holiday", "major", None)])
    r = client.post("/api/v1/platform/observances/import/analyze", headers=ctx["h"],
                    files={"file": ("dates.xlsx", data,
                                    "application/vnd.openxmlformats-officedocument."
                                    "spreadsheetml.sheet")})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "super_admin_only"


def test_upload_preview_then_save(client, cleanup):
    """Two calls on purpose: nothing is written until the operator has seen the
    rows, and the rows they confirmed are what gets written."""
    ctx = _org(client, cleanup)
    _make_super(ctx["user_id"])
    sh = ctx["h"]
    tag = uuid.uuid4().hex[:6]

    data = _sheet([
        (f"Alpha {tag}", "17/10/2028", None, "Kerala", "holiday", "major", "note one"),
        (f"Beta {tag}", "18 Oct 2028", None, "All India", "festival", "minor", None),
        (f"Broken {tag}", "nonsense", None, "Kerala", "holiday", "major", None),
    ])
    prev = client.post(
        "/api/v1/platform/observances/import/analyze?source=Test%20gazette%202028",
        headers=sh,
        files={"file": ("dates.xlsx", data,
                        "application/vnd.openxmlformats-officedocument."
                        "spreadsheetml.sheet")}).json()
    assert prev["ready"] == 2 and prev["blocked"] == 1

    good = [r for r in prev["rows"] if r["importable"]]
    body = {
        "mapping": {f: f for f in ("name", "date", "end_date", "states", "kind",
                                   "tier", "tradition", "prep_days", "note", "source")},
        "rows": [{"name": r["name"], "date": r["date"], "end_date": r["end_date"],
                  "kind": r["kind"], "tier": r["tier"],
                  "states": "|".join(r["states"] or []), "tradition": r["tradition"],
                  "prep_days": r["prep_days"], "note": r["note"], "source": r["source"]}
                 for r in good],
        "source": "Test gazette 2028",
    }
    saved = client.post("/api/v1/platform/observances/import/commit",
                        headers=sh, json=body).json()
    assert (saved["created"], saved["updated"]) == (2, 0)

    listed = client.get(f"/api/v1/platform/observances?q={tag}", headers=sh).json()
    assert len(listed) == 2
    for row in listed:
        cleanup["observances"].append(uuid.UUID(row["id"]))
    alpha = next(r for r in listed if r["name"].startswith("Alpha"))
    assert alpha["date"] == "2028-10-17" and alpha["states"] == ["Kerala"]
    assert alpha["source"] == "Test gazette 2028"

    # Re-running the same file corrects rather than duplicating (`S-151`).
    again = client.post("/api/v1/platform/observances/import/commit",
                        headers=sh, json=body).json()
    assert (again["created"], again["updated"]) == (0, 2)


def test_a_duplicate_inside_one_file_is_reported_not_silently_overwritten(client, cleanup):
    """`bulk()` upserts on (key, date), so two identical rows in one sheet would
    quietly collapse to one and the operator would never know the file was
    wrong. Same defect shape as V1-19, arriving from a spreadsheet."""
    ctx = _org(client, cleanup)
    _make_super(ctx["user_id"])
    tag = uuid.uuid4().hex[:6]
    name = f"Twice {tag}"
    body = {
        "mapping": {f: f for f in ("name", "date", "states", "kind", "tier", "source")},
        "rows": [
            {"name": name, "date": "2028-11-05", "states": "Kerala",
             "kind": "holiday", "tier": "major", "source": "s"},
            {"name": name, "date": "2028-11-05", "states": "Punjab",
             "kind": "holiday", "tier": "major", "source": "s"},
        ],
        "source": "dupe test",
    }
    out = client.post("/api/v1/platform/observances/import/commit",
                      headers=ctx["h"], json=body).json()
    assert out["created"] == 1
    assert len(out["duplicates"]) == 1 and name in out["duplicates"][0]

    listed = client.get(f"/api/v1/platform/observances?q={tag}", headers=ctx["h"]).json()
    assert len(listed) == 1
    cleanup["observances"].append(uuid.UUID(listed[0]["id"]))
    # The FIRST row won, and it was not silently replaced by the second.
    assert listed[0]["states"] == ["Kerala"]


# ── the school-side browse ───────────────────────────────────────────────────

def test_browse_defaults_to_the_school_state_and_all_is_explicit(client, cleanup):
    kerala = _org(client, cleanup, state="Kerala")
    _make_super(kerala["user_id"])
    h = kerala["h"]
    tag = uuid.uuid4().hex[:6]
    on = (date.today() + timedelta(days=30)).isoformat()

    for label, states in ((f"KL {tag}", ["Kerala"]), (f"PB {tag}", ["Punjab"]),
                          (f"IN {tag}", None)):
        r = client.post("/api/v1/platform/observances", headers=h, json={
            "key": f"{label.lower().replace(' ', '-')}", "name": label, "date": on,
            "kind": "holiday", "source": "V1-20 test", "states": states})
        cleanup["observances"].append(uuid.UUID(r.json()["id"]))

    # No `state` param → this school's own state, which is what the dropdown
    # shows before anybody touches it.
    default = client.get("/api/v1/events/catalogue", headers=h).json()
    assert default["org_state"] == "Kerala" and default["filter_state"] == "Kerala"
    names = {r["name"] for r in default["rows"]}
    assert f"KL {tag}" in names and f"IN {tag}" in names
    assert f"PB {tag}" not in names

    # `state=all` is the explicit "show me everything".
    every = client.get("/api/v1/events/catalogue?state=all", headers=h).json()
    assert every["filter_state"] is None
    every_names = {r["name"] for r in every["rows"]}
    assert {f"KL {tag}", f"PB {tag}", f"IN {tag}"} <= every_names
    # `applies_here` is what lets the table say which of these reach this school.
    by_name = {r["name"]: r for r in every["rows"]}
    assert by_name[f"KL {tag}"]["applies_here"] is True
    assert by_name[f"IN {tag}"]["applies_here"] is True
    assert by_name[f"PB {tag}"]["applies_here"] is False

    # Another state on demand.
    punjab = client.get("/api/v1/events/catalogue?state=Punjab", headers=h).json()
    assert f"PB {tag}" in {r["name"] for r in punjab["rows"]}

    # The dropdown's options come from the corpus, so it cannot offer a value
    # that returns nothing.
    assert "Kerala" in every["states"] and "Punjab" in every["states"]


def test_browse_shows_what_this_school_decided_and_no_platform_telemetry(client, cleanup):
    ctx = _org(client, cleanup, state="Kerala")
    _make_super(ctx["user_id"])
    h = ctx["h"]
    tag = uuid.uuid4().hex[:6]
    on = (date.today() + timedelta(days=20)).isoformat()

    made = client.post("/api/v1/platform/observances", headers=h, json={
        "key": f"decide-{tag}", "name": f"Decide {tag}", "date": on,
        "kind": "holiday", "source": "V1-20 test", "states": ["Kerala"]}).json()
    cleanup["observances"].append(uuid.UUID(made["id"]))

    before = next(r for r in client.get("/api/v1/events/catalogue", headers=h).json()["rows"]
                  if r["key"] == f"decide-{tag}")
    assert before["decided"] is False and before["approved"] is False
    # A school never receives how many OTHER schools acted on a row.
    assert "decided_count" not in before

    client.post(f"/api/v1/events/suggestions/{made['id']}/approve", headers=h, json={
        "start_date": on, "lock": "closed"})

    after = next(r for r in client.get("/api/v1/events/catalogue", headers=h).json()["rows"]
                 if r["key"] == f"decide-{tag}")
    assert after["decided"] is True and after["approved"] is True


def test_browse_is_admin_only(client, cleanup):
    """`D-57` — everything that leads to a decision is the admin's. A teacher's
    strip is never provisional (`Q-64` a)."""
    ctx = _org(client, cleanup)
    bulk = client.post("/api/v1/org/members/bulk", headers=ctx["h"], json={"members": [
        {"username": f"t{uuid.uuid4().hex[:8]}", "password": "supersecret1",
         "role": "teacher"}]})
    t = bulk.json()["results"][0]
    cleanup["users"].append(uuid.UUID(t["user_id"]))
    login = client.post("/api/v1/auth/login", json={
        "identifier": t["username"], "password": "supersecret1"}).json()
    th = {"Authorization": f"Bearer {login['access_token']}"}

    assert client.get("/api/v1/events/catalogue", headers=th).status_code == 403
    assert client.get("/api/v1/events/catalogue", headers=ctx["h"]).status_code == 200
