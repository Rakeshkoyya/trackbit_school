"""V1-19 — the observance corpus and per-state scoping.

What each test is defending:

  * **The defect the packet exists to close.** V1-7 built the catalogue tables,
    the approval sheet, the cost preview and the what's-on feed, and shipped the
    table EMPTY (`Q-63`). Every school's suggestions queue was blank, with
    nothing on screen to say why. There is now a curated corpus, and these tests
    are what stop it silently rotting.

  * **`UNIQUE(key, date)` made a per-state corpus impossible**, and failed
    *silently*: `bulk()` upserts, so importing "Onam · Kerala" and then "Onam ·
    Karnataka" did not error — the second overwrote the first, and the catalogue
    ended up asserting Onam is observed in exactly one state. `states` is now a
    set, and `collisions()` is the corpus checking itself for the shape that
    caused it.

  * **Free-text state was the whole feature's silent failure mode.**
    `organizations.state` is a text box. A school that typed `TN` matched no row,
    saw an empty feed, and nothing errored or logged. `normalise()` is the fix
    and it must never guess: unresolvable text means *no state*, which shows the
    all-India rows — thin, but never a school in Kerala reading Punjab's
    gazette.

  * **`source` is never decorative (`S-150`).** The admin approving a date is
    the last human in the chain. Every row must name where its date came from.

  * **A suggestion is still never a date (`D-79`).** The corpus does not change
    that contract: the admin edits the date at approval, which is the structural
    answer to almanacs that disagree by region.
"""

import uuid
from datetime import date, timedelta

import pytest

from app.core.indian_states import ALL_STATES, normalise, normalise_all, unresolved
from app.data.observances import available_years, build, collisions, summarise
from app.models import User
from tests.conftest import AdminSession

CURATED = (2026, 2027)


def _make_super(user_id: str) -> None:
    db = AdminSession()
    try:
        db.get(User, uuid.UUID(user_id)).is_super_admin = True
        db.commit()
    finally:
        db.close()


def _org(client, cleanup, *, state: str | None):
    """A school in a given state. `state` is written through the real settings
    endpoint, because that is the path a live school's value takes."""
    email = f"admin-{uuid.uuid4().hex[:12]}@example.com"
    reg = client.post("/api/v1/auth/register-org", json={
        "org_name": "Corpus Org", "name": "Director", "email": email,
        "password": "supersecret1", "timezone": "Asia/Kolkata"}).json()
    cleanup["orgs"].append(uuid.UUID(reg["org"]["id"]))
    cleanup["users"].append(uuid.UUID(reg["user"]["id"]))
    h = {"Authorization": f"Bearer {reg['access_token']}"}
    if state is not None:
        client.patch("/api/v1/org/settings", headers=h, json={"state": state})
    today = date.today()
    client.post("/api/v1/academics/years", headers=h, json={
        "label": "2026-27", "start_date": (today - timedelta(days=60)).isoformat(),
        "end_date": (today + timedelta(days=300)).isoformat()})
    return {"h": h, "org_id": reg["org"]["id"], "user_id": reg["user"]["id"]}


# ── the vocabulary ───────────────────────────────────────────────────────────

def test_state_normalisation_resolves_but_never_guesses():
    # Canonical spellings survive untouched — they are the storage tokens.
    for token in ALL_STATES:
        assert normalise(token) == token

    # The forms a real roster actually contains.
    assert normalise("TN") == "Tamil Nadu"
    assert normalise("tamilnadu") == "Tamil Nadu"
    assert normalise("  Tamil  Nadu  ") == "Tamil Nadu"
    assert normalise("Orissa") == "Odisha"
    assert normalise("Pondicherry") == "Puducherry"
    assert normalise("NCT of Delhi") == "Delhi"
    assert normalise("Uttaranchal") == "Uttarakhand"

    # And the rule that matters most: no fuzzy matching. A school that typed
    # something unusable gets NO state, not a plausible-looking wrong one — the
    # alternative is showing a Kerala school the Punjab holiday list.
    for junk in ("", "   ", None, "Kerela Ditsrict 4", "Zzz", "K"):
        assert normalise(junk) is None

    assert normalise_all(["TN", "orissa", "TN", "nonsense"]) == ["Tamil Nadu", "Odisha"]
    assert unresolved(["TN", "nonsense"]) == ["nonsense"]


# ── the corpus as data ───────────────────────────────────────────────────────

@pytest.mark.parametrize("year", CURATED)
def test_corpus_builds_and_never_collides(year):
    """A duplicate (key, date) does not raise on import — `bulk()` upserts, so
    the second row silently REPLACES the first. That is exactly the defect the
    packet fixed, so the corpus checks itself for it."""
    rows = build(year)
    assert len(rows) > 300, "corpus looks truncated"
    assert collisions(year) == []
    assert all(r.date.year == year for r in rows)
    assert rows == sorted(rows, key=lambda r: (r.date, r.name))


@pytest.mark.parametrize("year", CURATED)
def test_every_row_carries_provenance_and_a_canonical_state(year):
    for r in build(year):
        # `S-150` — an unattributed date is one an admin either approves blindly
        # or ignores entirely, and both are bad.
        assert r.source and r.source.strip(), f"{r.key} has no source"
        assert r.kind in ("holiday", "festival", "observance")
        assert r.tier in ("major", "minor")
        # A state token that is not canonical imports perfectly and then matches
        # no school, for a year, with nothing to indicate it.
        assert unresolved(r.states) == [], f"{r.key} names an unknown state"
        if r.end_date:
            assert r.end_date >= r.date


@pytest.mark.parametrize("year", CURATED)
def test_the_three_national_holidays_are_all_india(year):
    """Republic Day, Independence Day and Gandhi Jayanti are the only three of
    which "every state, no exceptions" is true — so they must never be scoped."""
    rows = {r.key: r for r in build(year)}
    for key in ("republic-day", "independence-day", "gandhi-jayanti"):
        assert rows[key].states is None, f"{key} must not be state-scoped"
        assert rows[key].kind == "holiday"


def test_every_state_and_ut_is_covered():
    """A school in any state must see something regional, or the state picker
    is a promise the corpus does not keep."""
    covered: set[str] = set()
    for year in CURATED:
        for r in build(year):
            covered.update(r.states or ())
    missing = [s for s in ALL_STATES if s not in covered]
    assert missing == [], f"no regional dates for: {missing}"


def test_regional_holidays_name_the_right_states():
    """Spot-checks against the state notifications the corpus was read from.
    These are the rows a wrong `states` list would make invisible to the school
    that most needs them."""
    rows = {r.key: r for r in build(2027)}
    assert "Kerala" in rows["onam"].states
    assert "Punjab" not in rows["onam"].states
    assert set(rows["pongal"].states) == {"Tamil Nadu", "Puducherry"}
    assert "Karnataka" in rows["ugadi"].states and "Maharashtra" in rows["ugadi"].states
    assert "Bihar" in rows["chhath-puja"].states
    assert "Assam" in rows["bohag-bihu"].states
    # Diwali is gazetted everywhere; scoping it would hide it from everyone.
    assert rows["diwali"].states is None


def test_fixed_dates_generate_for_an_uncurated_year():
    """`FIXED` is why extending the corpus is one afternoon, not a rebuild: a
    year with no curated MOVABLE block still returns every fixed date. The
    caller learns it has no festivals from `available_years()`, not from a
    silently thin list."""
    assert list(available_years()) == list(CURATED)
    future = build(2031)
    keys = {r.key for r in future}
    assert "republic-day" in keys and "childrens-day" in keys
    assert "diwali" not in keys, "a lunar date must never be generated by arithmetic"
    assert summarise(2031)["movable_curated"] is False
    assert summarise(2026)["movable_curated"] is True


def test_international_days_are_present_but_mostly_minor():
    """`S-125` — an international day exists for almost everything, and a feed
    with something on it every day stops being read. The whole UN list is here;
    the tier is what keeps it out of a school's way."""
    rows = build(2026)
    un = [r for r in rows if "United Nations" in r.source]
    assert len(un) > 150
    assert all(r.kind == "observance" and r.states is None for r in un)
    minor = [r for r in un if r.tier == "minor"]
    assert len(minor) > len(un) / 2, "the UN list must not flood the feed"
    major = {r.name for r in un if r.tier == "major"}
    assert "World Environment Day" in major
    assert "International Day of Yoga" in major
    assert "International Literacy Day" in major


# ── end to end, through the real endpoints ───────────────────────────────────

def test_bulk_import_is_idempotent_and_reports_unplaceable_states(client, cleanup):
    """Re-running a corrected file must FIX every school, never double-suggest
    to all of them (`S-151`) — and an unresolvable state must be reported, since
    it is the one failure here with no symptom."""
    ctx = _org(client, cleanup, state="Kerala")
    _make_super(ctx["user_id"])
    sh = ctx["h"]

    key = f"corpus-test-{uuid.uuid4().hex[:8]}"
    payload = {"source": "V1-19 test", "entries": [{
        "key": key, "name": "Test Festival", "date": "2027-04-07",
        "kind": "holiday", "tier": "major", "prep_days": 7,
        "states": ["Kerala", "TN", "not-a-state"], "source": "V1-19 test"}]}

    first = client.post("/api/v1/platform/observances/bulk", headers=sh, json=payload)
    assert first.status_code == 200, first.text
    assert first.json()["created"] == 1
    # Reported, not silently dropped.
    assert first.json()["unresolved_states"] == ["not-a-state"]

    second = client.post("/api/v1/platform/observances/bulk", headers=sh, json=payload)
    assert second.json()["created"] == 0 and second.json()["updated"] == 1

    listed = [o for o in client.get("/api/v1/platform/observances", headers=sh).json()
              if o["key"] == key]
    assert len(listed) == 1
    cleanup["observances"].append(uuid.UUID(listed[0]["id"]))
    # The alias was canonicalised on the way in; the junk never reached the row.
    assert listed[0]["states"] == ["Kerala", "Tamil Nadu"]


def test_suggestions_are_scoped_to_the_school_state(client, cleanup):
    """The point of the whole packet: a Kerala school is offered Onam and a
    Punjab school is not, and both are offered Diwali."""
    kerala = _org(client, cleanup, state="Kerala")
    _make_super(kerala["user_id"])
    sh = kerala["h"]

    on = date.today() + timedelta(days=20)
    for name, states in (("Onam Test", ["Kerala"]),
                         ("Baisakhi Test", ["Punjab"]),
                         ("Diwali Test", None)):
        body = {"key": f"{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:6]}",
                "name": name, "date": on.isoformat(), "kind": "holiday",
                "source": "V1-19 test", "states": states}
        r = client.post("/api/v1/platform/observances", headers=sh, json=body)
        assert r.status_code == 200, r.text
        cleanup["observances"].append(uuid.UUID(r.json()["id"]))

    seen = {s["name"] for s in client.get(
        "/api/v1/events/suggestions", headers=kerala["h"]).json()}
    assert "Onam Test" in seen
    assert "Diwali Test" in seen
    assert "Baisakhi Test" not in seen

    punjab = _org(client, cleanup, state="Punjab")
    seen_pb = {s["name"] for s in client.get(
        "/api/v1/events/suggestions", headers=punjab["h"]).json()}
    assert "Baisakhi Test" in seen_pb
    assert "Diwali Test" in seen_pb
    assert "Onam Test" not in seen_pb


def test_a_school_with_no_state_still_sees_all_india_rows(client, cleanup):
    """The old code compared `Observance.state == (org.state or "")`, so an
    unset school matched NOTHING and read exactly like an empty catalogue. A
    school we cannot place must see the national rows — thin, never wrong, and
    never silently blank."""
    ctx = _org(client, cleanup, state=None)
    _make_super(ctx["user_id"])
    on = date.today() + timedelta(days=15)

    for name, states in (("National Test Day", None), ("Kerala Only Test", ["Kerala"])):
        body = {"key": f"{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:6]}",
                "name": name, "date": on.isoformat(), "kind": "holiday",
                "source": "V1-19 test", "states": states}
        r = client.post("/api/v1/platform/observances", headers=ctx["h"], json=body)
        cleanup["observances"].append(uuid.UUID(r.json()["id"]))

    seen = {s["name"] for s in client.get(
        "/api/v1/events/suggestions", headers=ctx["h"]).json()}
    assert "National Test Day" in seen
    assert "Kerala Only Test" not in seen

    # An unusable value behaves the same as none at all — it does not fall back
    # to "show everything", which would be the wrong-calendar failure.
    client.patch("/api/v1/org/settings", headers=ctx["h"], json={"state": "Kerela!!"})
    seen2 = {s["name"] for s in client.get(
        "/api/v1/events/suggestions", headers=ctx["h"]).json()}
    assert "National Test Day" in seen2
    assert "Kerala Only Test" not in seen2
