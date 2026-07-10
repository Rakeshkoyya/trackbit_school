"""V2-P11: term-scoped planning.

The school knows the whole year's portion in April but sizes each term's chapters
when that term begins. That means three things must hold:

  * an unsized chapter is not scheduled, and nothing pretends it is (the old
    NOT NULL DEFAULT 1 made an unplanned year forecast green);
  * planning Term 2 must not rewrite Term 1's approved baseline (P2);
  * approval must be reversible, because a plan made in April gets re-planned in
    September — and the undo is an append, never a rewrite (law 3).
"""

import uuid
from datetime import date

from app.services.calendar import effective_periods
from app.services.plan_validate import validate_unsized
from app.services.planner import distribute

MON_SAT = [0, 1, 2, 3, 4, 5]


# ── pure ─────────────────────────────────────────────────────────────────────
def test_v6_unsized():
    assert validate_unsized([]) is None
    v = validate_unsized(["Integers"])
    assert v is not None and v.code == "unsized" and '"Integers"' in v.message
    v = validate_unsized(["Integers", "Fractions"])
    assert v is not None and "2 topics" in v.message


def test_straddling_week_is_costed_at_its_in_window_days():
    """Term 2 opens on Thursday 1 Oct. That week has 3 teaching days, not 6, so it
    must yield half a week's periods — otherwise the planner crams a week of topics
    into three days and the whole term schedules early."""
    week = date(2026, 9, 28)  # Monday; Oct 1 is the Thursday
    got = effective_periods(6, week, working_weekdays=MON_SAT, blocked=set(),
                            year_start=date(2026, 10, 1), year_end=date(2027, 3, 31))
    assert got == 3.0

    # A week wholly inside the window is unaffected by that rule.
    inside = effective_periods(6, date(2026, 11, 2), working_weekdays=MON_SAT, blocked=set(),
                               year_start=date(2026, 10, 1), year_end=date(2027, 3, 31))
    assert inside == 6.0


def test_distribute_stays_inside_the_term_window():
    weeks = distribute([3, 3, 4], periods_per_week=6, working_weekdays=MON_SAT, blocked=set(),
                       window_start=date(2026, 10, 1), window_end=date(2027, 3, 31))
    assert all(w >= date(2026, 9, 28) for w in weeks)   # never before the term's week
    assert all(w <= date(2027, 3, 29) for w in weeks)   # never past its last week
    # The same topics over the whole year start in April instead.
    year = distribute([3, 3, 4], periods_per_week=6, working_weekdays=MON_SAT, blocked=set(),
                      window_start=date(2026, 4, 1), window_end=date(2027, 3, 31))
    assert year[0] < date(2026, 5, 1)


# ── integration ──────────────────────────────────────────────────────────────
def _setup(client, cleanup):
    email = f"admin-{uuid.uuid4().hex[:12]}@example.com"
    reg = client.post("/api/v1/auth/register-org",
                      json={"org_name": "Term Org", "name": "Director", "email": email,
                            "password": "supersecret1", "timezone": "Asia/Kolkata"}).json()
    cleanup["orgs"].append(uuid.UUID(reg["org"]["id"]))
    cleanup["users"].append(uuid.UUID(reg["user"]["id"]))
    h = {"Authorization": f"Bearer {reg['access_token']}"}
    year = client.post("/api/v1/academics/years", headers=h,
                       json={"label": "2026-27", "start_date": "2026-04-01",
                             "end_date": "2027-03-31"}).json()
    t1 = client.post("/api/v1/academics/terms", headers=h,
                     json={"academic_year_id": year["id"], "name": "Term 1",
                           "start_date": "2026-04-01", "end_date": "2026-09-30"}).json()
    t2 = client.post("/api/v1/academics/terms", headers=h,
                     json={"academic_year_id": year["id"], "name": "Term 2",
                           "start_date": "2026-10-01", "end_date": "2027-03-31"}).json()
    klass = client.post("/api/v1/academics/classes", headers=h,
                        json={"academic_year_id": year["id"], "name": "6", "section": "A"}).json()
    subject = client.post("/api/v1/academics/subjects", headers=h,
                          json={"name": "Mathematics"}).json()
    cs = client.post("/api/v1/academics/class-subjects", headers=h,
                     json={"class_id": klass["id"], "subject_id": subject["id"],
                           "periods_per_week": 6}).json()
    return h, year, klass, cs, t1, t2


def _unit(client, h, cs_id, title, term_id, topics):
    """topics = [(title, est_or_None)]"""
    u = client.post("/api/v1/planner/syllabus/units", headers=h,
                    json={"class_subject_id": cs_id, "title": title, "term_id": term_id}).json()
    for t_title, est in topics:
        body = {"unit_id": u["id"], "title": t_title}
        if est is not None:
            body["est_periods"] = est
        r = client.post("/api/v1/planner/syllabus/topics", headers=h, json=body)
        assert r.status_code == 200, r.text
    return u


def _termwise(client, h, cs_id, t1, t2):
    """The real shape: Term 1 sized, Term 2 recorded but unsized."""
    _unit(client, h, cs_id, "Knowing Our Numbers", t1["id"], [("Comparing", 3), ("Rounding", 2)])
    _unit(client, h, cs_id, "Integers", t2["id"], [("Negatives", None), ("Adding", None)])


def test_unsized_chapters_are_recorded_but_never_scheduled(client, cleanup):
    h, _y, _k, cs, t1, t2 = _setup(client, cleanup)
    _termwise(client, h, cs["id"], t1, t2)

    gen = client.post(f"/api/v1/planner/plan/{cs['id']}/generate?term_id={t1['id']}", headers=h)
    assert gen.status_code == 200, gen.text
    plan = gen.json()["plan"]
    # Only Term 1's two topics are scheduled; Term 2's two are recorded, unsized.
    assert len(plan["entries"]) == 2
    assert plan["unestimated_topics"] == 2
    assert plan["total_est_periods"] == 5  # 3 + 2, the unsized ones contribute nothing


def test_whole_year_generate_reports_unsized_and_does_not_fit(client, cleanup):
    h, _y, _k, cs, t1, t2 = _setup(client, cleanup)
    _termwise(client, h, cs["id"], t1, t2)

    gen = client.post(f"/api/v1/planner/plan/{cs['id']}/generate", headers=h).json()
    codes = {v["code"] for v in gen["violations"]}
    assert "unsized" in codes
    # A plan that quietly omits half the syllabus has not been made to fit.
    assert gen["fits"] is False


def test_forecast_is_unplanned_not_green_while_chapters_are_unsized(client, cleanup):
    """The bug this packet exists to kill: est_periods NOT NULL DEFAULT 1 meant the
    unsized Term-2 chapters were planned as 1 period each, baseline == projected,
    weeks_behind == 0, and the director's dashboard went green on an unplanned year."""
    h, _y, klass, cs, t1, t2 = _setup(client, cleanup)
    _termwise(client, h, cs["id"], t1, t2)
    client.post(f"/api/v1/planner/plan/{cs['id']}/generate?term_id={t1['id']}", headers=h)

    rows = client.get(f"/api/v1/planner/plan/forecast?class_id={klass['id']}", headers=h).json()
    row = next(r for r in rows if r["class_subject_id"] == cs["id"])
    assert row["status"] == "unplanned"
    assert row["status"] != "green"
    assert row["unestimated_topics"] == 2
    assert row["projected_finish"] is None  # no honest finish date exists


def test_planning_term_2_does_not_touch_approved_term_1(client, cleanup):
    """P2: the approved baseline is not rewritten by a later term's planning."""
    h, _y, _k, cs, t1, t2 = _setup(client, cleanup)
    _termwise(client, h, cs["id"], t1, t2)

    client.post(f"/api/v1/planner/plan/{cs['id']}/generate?term_id={t1['id']}", headers=h)
    ok = client.post(f"/api/v1/planner/plan/{cs['id']}/approve?term_id={t1['id']}", headers=h)
    assert ok.status_code == 200, ok.text
    assert ok.json()["status"] == "partial"  # Term 2 still open
    t1_entries = {e["topic_id"]: e["week_start"] for e in ok.json()["entries"]}

    # September arrives: size Term 2's chapters, then plan just that term.
    syllabus = client.get(f"/api/v1/planner/syllabus?class_subject_id={cs['id']}",
                          headers=h).json()
    t2_topics = [t for u in syllabus if u["term_id"] == t2["id"] for t in u["topics"]]
    for t in t2_topics:
        r = client.put(f"/api/v1/planner/syllabus/topics/{t['id']}/estimate", headers=h,
                       json={"est_periods": 4})
        assert r.status_code == 200, r.text

    gen = client.post(f"/api/v1/planner/plan/{cs['id']}/generate?term_id={t2['id']}", headers=h)
    assert gen.status_code == 200, gen.text
    plan = gen.json()["plan"]

    after = {e["topic_id"]: e["week_start"] for e in plan["entries"]}
    for topic_id, week in t1_entries.items():
        assert after[topic_id] == week, "Term 1's approved baseline was rewritten"
    # Term 2's topics are scheduled inside Term 2.
    for t in t2_topics:
        assert after[t["id"]] >= "2026-09-28"
    assert plan["unestimated_topics"] == 0


def test_approved_term_is_locked_and_unapprove_is_an_append(client, cleanup):
    h, _y, _k, cs, t1, t2 = _setup(client, cleanup)
    _termwise(client, h, cs["id"], t1, t2)
    client.post(f"/api/v1/planner/plan/{cs['id']}/generate?term_id={t1['id']}", headers=h)
    client.post(f"/api/v1/planner/plan/{cs['id']}/approve?term_id={t1['id']}", headers=h)

    # Locked: re-generating that term is refused.
    blocked = client.post(f"/api/v1/planner/plan/{cs['id']}/generate?term_id={t1['id']}",
                          headers=h)
    assert blocked.status_code == 400
    assert "locked" in blocked.json()["error"]["message"].lower()

    # ...and so is quietly re-sizing a chapter underneath it.
    syllabus = client.get(f"/api/v1/planner/syllabus?class_subject_id={cs['id']}",
                          headers=h).json()
    t1_topic = next(t for u in syllabus if u["term_id"] == t1["id"] for t in u["topics"])
    r = client.put(f"/api/v1/planner/syllabus/topics/{t1_topic['id']}/estimate", headers=h,
                   json={"est_periods": 9})
    assert r.status_code == 400

    # Un-approve, then re-plan. The undo is a compensating row, not a rewrite.
    un = client.post(f"/api/v1/planner/plan/{cs['id']}/unapprove?term_id={t1['id']}", headers=h)
    assert un.status_code == 200, un.text
    assert un.json()["status"] == "draft"
    again = client.post(f"/api/v1/planner/plan/{cs['id']}/generate?term_id={t1['id']}", headers=h)
    assert again.status_code == 200

    # Un-approving something that isn't approved is an error, not a silent no-op.
    assert client.post(f"/api/v1/planner/plan/{cs['id']}/unapprove?term_id={t2['id']}",
                       headers=h).status_code == 400


def test_cannot_approve_a_term_with_unsized_chapters(client, cleanup):
    """Locking a baseline that omits chapters would make the forecast confidently wrong."""
    h, _y, _k, cs, t1, t2 = _setup(client, cleanup)
    _termwise(client, h, cs["id"], t1, t2)
    client.post(f"/api/v1/planner/plan/{cs['id']}/generate?term_id={t2['id']}", headers=h)
    r = client.post(f"/api/v1/planner/plan/{cs['id']}/approve?term_id={t2['id']}", headers=h)
    assert r.status_code == 400
    assert "no period estimate" in r.json()["error"]["message"]


def test_whole_year_replan_refused_while_a_term_is_approved(client, cleanup):
    h, _y, _k, cs, t1, t2 = _setup(client, cleanup)
    _termwise(client, h, cs["id"], t1, t2)
    client.post(f"/api/v1/planner/plan/{cs['id']}/generate?term_id={t1['id']}", headers=h)
    client.post(f"/api/v1/planner/plan/{cs['id']}/approve?term_id={t1['id']}", headers=h)

    r = client.post(f"/api/v1/planner/plan/{cs['id']}/generate", headers=h)
    assert r.status_code == 400
    assert "individually" in r.json()["error"]["message"]


def test_term_1_exam_stays_validated_while_term_2_is_generated(client, cleanup):
    """V5 must read the persisted baseline for terms it isn't planning. Building the
    portion from only the current slice reported a locked, fully-planned Term 1 as
    "not scheduled at all" the moment Term 2 was generated."""
    h, year, _k, cs, t1, t2 = _setup(client, cleanup)
    _termwise(client, h, cs["id"], t1, t2)
    client.post(f"/api/v1/planner/plan/{cs['id']}/generate?term_id={t1['id']}", headers=h)
    client.post(f"/api/v1/planner/plan/{cs['id']}/approve?term_id={t1['id']}", headers=h)

    # A Term-1 exam whose portion is all of Term 1's chapters.
    syllabus = client.get(f"/api/v1/planner/syllabus?class_subject_id={cs['id']}", headers=h).json()
    t1_topics = [t for u in syllabus if u["term_id"] == t1["id"] for t in u["topics"]]
    exam = client.post("/api/v1/academics/calendar/events", headers=h,
                       json={"academic_year_id": year["id"], "type": "exam_block",
                             "title": "Half-yearly", "start_date": "2026-09-21",
                             "end_date": "2026-09-30"}).json()
    r = client.post("/api/v1/academics/exam-portions", headers=h,
                    json={"exam_event_id": exam["id"], "class_subject_id": cs["id"],
                          "upto_topic_id": t1_topics[-1]["id"]})
    assert r.status_code == 200, r.text

    # Size Term 2 and generate it. Term 1 is planned and locked, so the exam is safe.
    t2_topics = [t for u in syllabus if u["term_id"] == t2["id"] for t in u["topics"]]
    for t in t2_topics:
        client.put(f"/api/v1/planner/syllabus/topics/{t['id']}/estimate", headers=h,
                   json={"est_periods": 4})
    gen = client.post(f"/api/v1/planner/plan/{cs['id']}/generate?term_id={t2['id']}",
                      headers=h).json()
    messages = " ".join(v["message"] for v in gen["violations"])
    assert "not scheduled at all" not in messages, messages


def test_unsizing_a_planned_topic_drops_its_plan_entry(client, cleanup):
    """A topic that was sized, planned, then un-sized must lose its entry — otherwise
    the plan keeps scheduling a chapter nobody has estimated."""
    h, _y, _k, cs, t1, _t2 = _setup(client, cleanup)
    _unit(client, h, cs["id"], "Numbers", t1["id"], [("Comparing", 3), ("Rounding", 2)])
    plan = client.post(f"/api/v1/planner/plan/{cs['id']}/generate?term_id={t1['id']}",
                       headers=h).json()["plan"]
    assert len(plan["entries"]) == 2

    syllabus = client.get(f"/api/v1/planner/syllabus?class_subject_id={cs['id']}", headers=h).json()
    victim = syllabus[0]["topics"][1]
    client.put(f"/api/v1/planner/syllabus/topics/{victim['id']}/estimate", headers=h,
               json={"est_periods": None})

    plan = client.post(f"/api/v1/planner/plan/{cs['id']}/generate?term_id={t1['id']}",
                       headers=h).json()["plan"]
    assert len(plan["entries"]) == 1
    assert victim["id"] not in {e["topic_id"] for e in plan["entries"]}
    assert plan["unestimated_topics"] == 1


def test_plan_reports_a_row_per_term(client, cleanup):
    h, _y, _k, cs, t1, t2 = _setup(client, cleanup)
    _termwise(client, h, cs["id"], t1, t2)
    client.post(f"/api/v1/planner/plan/{cs['id']}/generate?term_id={t1['id']}", headers=h)
    client.post(f"/api/v1/planner/plan/{cs['id']}/approve?term_id={t1['id']}", headers=h)

    terms = client.get(f"/api/v1/planner/plan?class_subject_id={cs['id']}", headers=h).json()["terms"]
    by_name = {t["name"]: t for t in terms}
    assert by_name["Term 1"]["approved"] is True
    assert by_name["Term 1"]["unestimated_topics"] == 0
    assert by_name["Term 2"]["approved"] is False
    assert by_name["Term 2"]["unestimated_topics"] == 2


def test_whole_year_school_is_unaffected(client, cleanup):
    """No terms on any chapter → the original behaviour, approve locks the year."""
    h, _y, klass, cs, _t1, _t2 = _setup(client, cleanup)
    _unit(client, h, cs["id"], "Unit 1", None, [("Cells", 2), ("Tissues", 2), ("Organs", 3)])

    gen = client.post(f"/api/v1/planner/plan/{cs['id']}/generate", headers=h).json()
    assert gen["fits"] is True and gen["violations"] == []
    assert len(gen["plan"]["entries"]) == 3
    assert gen["plan"]["terms"] == [] or gen["plan"]["terms"][0]["name"] == "Whole year"

    ap = client.post(f"/api/v1/planner/plan/{cs['id']}/approve", headers=h)
    assert ap.status_code == 200 and ap.json()["status"] == "approved"
    assert client.post(f"/api/v1/planner/plan/{cs['id']}/generate", headers=h).status_code == 400

    rows = client.get(f"/api/v1/planner/plan/forecast?class_id={klass['id']}", headers=h).json()
    assert next(r for r in rows if r["class_subject_id"] == cs["id"])["status"] == "green"
