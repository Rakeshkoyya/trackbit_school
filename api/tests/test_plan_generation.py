"""V2-P5: plan generation pipeline — the 4 deterministic validators, over-capacity
as a human decision, teacher change-request round-trip (SPRD2 §5.2)."""

import uuid
from datetime import date

from app.services.plan_validate import (
    validate_capacity,
    validate_coverage,
    validate_ordering,
    validate_teacher_load,
)


# ── V1–V4 validators (pure, no DB) ───────────────────────────────────────────
def test_v1_capacity():
    assert validate_capacity(10, 40) is None
    v = validate_capacity(50, 40)
    assert v is not None and v.code == "capacity" and "trim topics" in v.message


def test_v2_coverage():
    end = date(2027, 3, 29)  # a Monday
    assert validate_coverage([date(2026, 4, 6), date(2026, 9, 7)], end) is None
    v = validate_coverage([date(2027, 4, 5)], end)  # past year end
    assert v is not None and v.code == "coverage"


def test_v3_ordering():
    assert validate_ordering([date(2026, 4, 6), date(2026, 4, 13), date(2026, 4, 13)]) is None
    v = validate_ordering([date(2026, 4, 13), date(2026, 4, 6)])  # goes backwards
    assert v is not None and v.code == "ordering"


def test_v4_teacher_load():
    wk = date(2026, 4, 6)
    assert validate_teacher_load({wk: 4}, 5) == []
    out = validate_teacher_load({wk: 7}, 5, teacher="Priya")
    assert len(out) == 1 and out[0].code == "teacher_load" and "Priya" in out[0].message


# ── generation + comments (integration) ──────────────────────────────────────
def _setup(client, cleanup):
    email = f"admin-{uuid.uuid4().hex[:12]}@example.com"
    reg = client.post("/api/v1/auth/register-org",
                      json={"org_name": "Gen Org", "name": "Director", "email": email,
                            "password": "supersecret1", "timezone": "Asia/Kolkata"}).json()
    cleanup["orgs"].append(uuid.UUID(reg["org"]["id"]))
    cleanup["users"].append(uuid.UUID(reg["user"]["id"]))
    h = {"Authorization": f"Bearer {reg['access_token']}"}
    year = client.post("/api/v1/academics/years", headers=h,
                       json={"label": "2026-27", "start_date": "2026-04-01",
                             "end_date": "2027-03-31"}).json()
    klass = client.post("/api/v1/academics/classes", headers=h,
                        json={"academic_year_id": year["id"], "name": "6", "section": "A"}).json()
    subject = client.post("/api/v1/academics/subjects", headers=h, json={"name": "Science"}).json()
    cs = client.post("/api/v1/academics/class-subjects", headers=h,
                     json={"class_id": klass["id"], "subject_id": subject["id"],
                           "periods_per_week": 5}).json()
    return h, year, klass, cs


def _syllabus(client, h, cs_id, topics):
    unit = client.post("/api/v1/planner/syllabus/units", headers=h,
                       json={"class_subject_id": cs_id, "title": "Unit 1"}).json()
    for title, est in topics:
        client.post("/api/v1/planner/syllabus/topics", headers=h,
                    json={"unit_id": unit["id"], "title": title, "est_periods": est})


def test_generate_fits_and_produces_ordered_plan(client, cleanup):
    h, _year, _klass, cs = _setup(client, cleanup)
    _syllabus(client, h, cs["id"], [("Cells", 2), ("Tissues", 2), ("Organs", 3)])
    gen = client.post(f"/api/v1/planner/plan/{cs['id']}/generate", headers=h)
    assert gen.status_code == 200, gen.text
    body = gen.json()
    assert body["fits"] is True
    assert not any(v["code"] == "capacity" for v in body["violations"])
    weeks = [e["week_start"] for e in body["plan"]["entries"]]
    assert weeks == sorted(weeks) and len(weeks) == 3


def test_over_capacity_is_reported_not_squeezed(client, cleanup):
    h, _year, _klass, cs = _setup(client, cleanup)
    # 12 chapters × 40 periods = 480 needed, but ~5/wk × ~52wks ≈ 260 available.
    _syllabus(client, h, cs["id"], [(f"Ch{i}", 40) for i in range(12)])
    gen = client.post(f"/api/v1/planner/plan/{cs['id']}/generate", headers=h).json()
    assert gen["fits"] is False
    assert any(v["code"] == "capacity" for v in gen["violations"])
    # still drafted for review (never silently dropped)
    assert len(gen["plan"]["entries"]) == 12


def test_teacher_change_request_round_trip(client, cleanup):
    h, _year, _klass, cs = _setup(client, cleanup)
    _syllabus(client, h, cs["id"], [("Cells", 2), ("Tissues", 2)])
    client.post(f"/api/v1/planner/plan/{cs['id']}/generate", headers=h)

    # teacher raises a change request
    c = client.post(f"/api/v1/planner/plan/{cs['id']}/comments", headers=h,
                    json={"text": "Chapter 4 needs more days"})
    assert c.status_code == 200, c.text
    comment_id = c.json()["id"]
    assert c.json()["status"] == "open"

    openc = client.get(f"/api/v1/planner/plan/{cs['id']}/comments", headers=h).json()
    assert len(openc) == 1

    # admin adjusts (re-generate) then resolves + re-approves
    client.post(f"/api/v1/planner/plan/{cs['id']}/generate", headers=h)
    res = client.post(f"/api/v1/planner/plan/comments/{comment_id}/resolve", headers=h)
    assert res.status_code == 200 and res.json()["status"] == "resolved"
    assert client.get(f"/api/v1/planner/plan/{cs['id']}/comments", headers=h).json() == []
    approve = client.post(f"/api/v1/planner/plan/{cs['id']}/approve", headers=h)
    assert approve.status_code == 200 and approve.json()["status"] == "approved"
