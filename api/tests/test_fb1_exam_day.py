"""FB-1a — an exam day is a school day.

The defect this file exists to keep dead:

SHANA International School ran PA2. `day_lock()` closed a day for ANY whole-day
event that affected teaching, and the setup pack marks an `exam_block` as
affecting teaching — so every teacher opened My Day during exam week and read

    School is closed today · PA2
    Nothing to mark or log. Enjoy it.

on a morning when the children were in the building sitting a paper. They
believed it and stopped logging. The admin then opened his dashboard, saw an
empty syllabus board and "all exam data is missing", and chased his mentors for
a fortnight about a gap the product had created.

So: **a holiday closes the school; an exam block does not.** The register is
still owed on an exam day. The timetabled lesson is not — nothing may nag a
teacher for a topic she could not have taught.
"""

from datetime import date, timedelta

from tests.test_assembly_register import _invite_teacher
from tests.test_events_v1_7 import _setup, _timetable


def _event(client, h, ctx, *, kind: str, title: str):
    r = client.post("/api/v1/academics/calendar/events", headers=h, json={
        "academic_year_id": ctx["year"]["id"], "type": kind, "title": title,
        "start_date": date.today().isoformat(), "end_date": date.today().isoformat()})
    assert r.status_code in (200, 201), r.text
    return r.json()


def test_an_exam_block_does_not_close_the_school(client, cleanup):
    """The whole of `FB-1a` in one assertion pair: `day_closed` stays False and
    the periods stay on her surface, so she can still take the roll."""
    ctx = _setup(client, cleanup)
    h, th = ctx["h"], ctx["th"]
    _timetable(client, h, ctx)

    before = client.get("/api/v1/classroom/my-day", headers=th).json()
    if not before["periods"]:
        return  # today is not a working weekday for this school
    assert before["day_closed"] is False and before["exam_day"] is False

    _event(client, h, ctx, kind="exam_block", title="PA2")

    day = client.get("/api/v1/classroom/my-day", headers=th).json()
    assert day["day_closed"] is False, "an exam is not a closure"
    assert day["exam_day"] is True and day["exam_title"] == "PA2"
    # The periods survive — this is the line that was costing the school its data.
    assert len(day["periods"]) == len(before["periods"])


def test_a_holiday_still_closes_the_school(client, cleanup):
    """The other half. `FB-1a` narrows what closes a day; it must not stop a
    real holiday from closing it, or 15 August invents work for everybody."""
    ctx = _setup(client, cleanup)
    h, th = ctx["h"], ctx["th"]
    _timetable(client, h, ctx)
    if not client.get("/api/v1/classroom/my-day", headers=th).json()["periods"]:
        return

    _event(client, h, ctx, kind="holiday", title="Independence Day")

    day = client.get("/api/v1/classroom/my-day", headers=th).json()
    assert day["day_closed"] is True and day["periods"] == []
    assert day["exam_day"] is False


def test_the_register_is_still_taken_on_an_exam_day(client, cleanup):
    """`locked` blanks the whole capture body, so on an exam day it must be
    False — otherwise the card says "nothing is being asked of you" and the roll
    never gets taken."""
    ctx = _setup(client, cleanup)
    h, th = ctx["h"], ctx["th"]
    _timetable(client, h, ctx)
    if not client.get("/api/v1/classroom/my-day", headers=th).json()["periods"]:
        return

    _event(client, h, ctx, kind="exam_block", title="PA2")

    card = client.get("/api/v1/periods/card", headers=th, params={
        "class_id": ctx["class"]["id"], "period_no": 1}).json()
    assert card["locked"] is False, "an exam day still wants its register"
    assert card["exam_day"] is True and card["exam_title"] == "PA2"

    # And a holiday still closes the card, reason and all.
    _event(client, h, ctx, kind="holiday", title="Independence Day")
    shut = client.get("/api/v1/periods/card", headers=th, params={
        "class_id": ctx["class"]["id"], "period_no": 1}).json()
    assert shut["locked"] is True


def _briefing(client, h) -> dict:
    """Force a fresh generation — `GET /daily` serves a cached row, and the
    whole point here is what today's rules produce."""
    r = client.post("/api/v1/reports/daily/regenerate", headers=h,
                    params={"on_date": date.today().isoformat()})
    assert r.status_code == 200, r.text
    return r.json()


def _section(report: dict, heading: str) -> str:
    for s in report.get("sections") or []:
        if s["heading"].lower() == heading.lower():
            return " ".join(s.get("lines") or [])
    return ""


def test_the_briefing_asks_for_no_lesson_logs_on_an_exam_day(client, cleanup):
    """`FB-1a`. "0 of 21 timetabled classes logged" on a PA2 morning is a true
    number answering a question nobody asked, and it is what convinced an admin
    his staff had stopped working."""
    ctx = _setup(client, cleanup)
    h = ctx["h"]
    _timetable(client, h, ctx)

    _event(client, h, ctx, kind="exam_block", title="PA2")

    teaching = _section(_briefing(client, h), "teaching")
    assert "PA2" in teaching, teaching
    assert "no timetabled lessons" in teaching, teaching
    assert "Not logged" not in teaching


def test_the_briefing_never_prints_a_question_mark_for_a_block(client, cleanup):
    """`FB-1e`. A block — assembly, games, a hostel session — has no
    class-subject (TT-2), and every one of them used to arrive in the teaching
    sets as a `None` and render as "? had attendance but no lesson log". The
    21 August briefing went to the school reading exactly that, and each block
    also counted as one more "unlogged class" in the denominator above it.
    """
    ctx = _setup(client, cleanup)
    h = ctx["h"]
    _timetable(client, h, ctx, periods=(1, 2, 3))

    block = client.post("/api/v1/timetable/blocks", headers=h, json={
        "name": "Morning assembly", "kind": "assembly"})
    assert block.status_code in (200, 201), block.text
    r = client.put("/api/v1/timetable/slot", headers=h, json={
        "class_id": ctx["class"]["id"], "weekday": date.today().weekday(),
        "period_no": 4, "slot_type": "block", "session_id": block.json()["id"],
        "effective_from": (date.today() - timedelta(days=30)).isoformat()})
    assert r.status_code == 200, r.text

    report = _briefing(client, h)
    lines = [ln for s in (report.get("sections") or []) for ln in (s.get("lines") or [])]
    lines += (report["highlights"].get("ambiguities") or [])
    lines += (report["highlights"].get("risks") or [])
    for line in lines:
        assert "?" not in line, f"placeholder leaked into the briefing: {line}"

    # …and the block is not one of the "timetabled classes" it says are unlogged.
    # The denominator counts distinct class-SUBJECTS, so this school owes one
    # (Maths, in three periods). Before the fix the block arrived as a `None`
    # and made it two — the second one rendering as "?".
    teaching = _section(report, "teaching")
    assert "timetabled classes logged" in teaching, teaching
    total = int(teaching.split(" of ")[1].split()[0])
    assert total == 1, f"the assembly was counted as a class to log: {teaching}"


def test_an_exam_confined_to_named_periods_is_still_only_those_periods(client, cleanup):
    """An exam in periods 1-2 is an ordinary partial lock and must not stand the
    whole day down — `_exam` only fires for a WHOLE-day block."""
    ctx = _setup(client, cleanup)
    h, th = ctx["h"], ctx["th"]
    _timetable(client, h, ctx)
    if not client.get("/api/v1/classroom/my-day", headers=th).json()["periods"]:
        return

    client.post("/api/v1/academics/calendar/events", headers=h, json={
        "academic_year_id": ctx["year"]["id"], "type": "exam_block",
        "title": "Maths paper", "start_date": date.today().isoformat(),
        "end_date": date.today().isoformat(), "blocks_periods": [1, 2]})

    day = client.get("/api/v1/classroom/my-day", headers=th).json()
    assert day["exam_day"] is False and day["day_closed"] is False
    assert day["locked_periods"] == [1, 2]
    assert all(p["period_no"] not in (1, 2) for p in day["periods"])


# ── `FB-1a` the off-timetable recorder ───────────────────────────────────────
def test_a_teacher_with_an_empty_day_can_still_record_a_class(client, cleanup):
    """The feature the exam-week silence asked for.

    Her grid has nothing today. She taught anyway — an extra class, a swap, a
    room she covered. Before this there was nowhere to put it, so it was lost,
    and the syllabus board read 3% while the teaching had actually happened.
    """
    ctx = _setup(client, cleanup)
    th = ctx["th"]
    # Deliberately NO timetable: this is the empty day.

    r = client.get("/api/v1/periods/recordable", headers=th)
    assert r.status_code == 200, r.text
    offer = r.json()
    mine = next(c for c in offer["classes"] if c["class_id"] == ctx["class"]["id"])
    assert [s["class_subject_id"] for s in mine["subjects"]] == [ctx["cs"]["id"]]
    assert [p["period_no"] for p in offer["periods"]] == [1, 2, 3, 4]

    # She picks class + subject + period, and lands on the ORDINARY card.
    card = client.get("/api/v1/periods/card", headers=th, params={
        "class_id": ctx["class"]["id"], "period_no": 3,
        "class_subject_id": ctx["cs"]["id"]})
    assert card.status_code == 200, card.text
    assert card.json()["class_subject_id"] == ctx["cs"]["id"]
    assert card.json()["subject_name"], "the card must name the subject she picked"

    # …and it records like any other period: the roll, then the lesson.
    marked = client.post("/api/v1/attendance/mark", headers=th, json={
        "class_id": ctx["class"]["id"], "period_no": 3,
        "class_subject_id": ctx["cs"]["id"], "exceptions": []})
    assert marked.status_code == 200, marked.text

    logged = client.post("/api/v1/classroom/lesson-logs", headers=th, json={
        "class_subject_id": ctx["cs"]["id"], "coverage": "full", "period_no": 3})
    assert logged.status_code in (200, 201), logged.text

    after = client.get("/api/v1/periods/card", headers=th, params={
        "class_id": ctx["class"]["id"], "period_no": 3}).json()
    assert after["attendance_marked"] is True
    # The subject sticks without being passed again — the opened period now
    # carries it, which is why `class_subject_id` is a fallback and not a flag.
    assert after["class_subject_id"] == ctx["cs"]["id"]


def test_the_recorder_offers_only_what_the_card_will_accept(client, cleanup):
    """A picker that lists a class the card then 403s is the "Loading roster…"
    bug wearing a different hat. The offer and the guard are one rule."""
    ctx = _setup(client, cleanup)
    h, th = ctx["h"], ctx["th"]

    other = client.post("/api/v1/academics/classes", headers=h, json={
        "academic_year_id": ctx["year"]["id"], "name": "9", "section": "C"}).json()

    offer = client.get("/api/v1/periods/recordable", headers=th).json()
    assert other["id"] not in [c["class_id"] for c in offer["classes"]]

    refused = client.get("/api/v1/periods/card", headers=th, params={
        "class_id": other["id"], "period_no": 1})
    assert refused.status_code == 403, refused.text


def test_a_class_teacher_with_no_subjects_may_still_record_her_own_class(client, cleanup):
    """SHANA's 11-A and 12-A have zero `class_subjects`. `visible_class_ids` has
    counted the homeroom since 2026-08-05 and `assert_can_take_class` did not,
    so her own class appeared on her board and then refused her the register."""
    ctx = _setup(client, cleanup)
    h = ctx["h"]

    mid, hh = _invite_teacher(client, cleanup, h, "Homeroom Only")
    bare = client.post("/api/v1/academics/classes", headers=h, json={
        "academic_year_id": ctx["year"]["id"], "name": "11", "section": "A",
        "class_teacher_member_id": mid}).json()

    offer = client.get("/api/v1/periods/recordable", headers=hh).json()
    row = next((c for c in offer["classes"] if c["class_id"] == bare["id"]), None)
    assert row is not None, "her own homeroom must be recordable"
    assert row["subjects"] == [], "she teaches none of its subjects — register only"

    card = client.get("/api/v1/periods/card", headers=hh, params={
        "class_id": bare["id"], "period_no": 1})
    assert card.status_code == 200, card.text

    marked = client.post("/api/v1/attendance/mark", headers=hh, json={
        "class_id": bare["id"], "period_no": 1, "exceptions": []})
    assert marked.status_code == 200, marked.text


def test_the_recorder_never_relabels_a_lesson_that_already_happened(client, cleanup):
    """`class_subject_id` is a fallback. An opened period already knows what it
    was, and a caller passing a different subject must not overwrite it."""
    ctx = _setup(client, cleanup)
    h, th = ctx["h"], ctx["th"]
    _timetable(client, h, ctx)

    subject2 = client.post("/api/v1/academics/subjects", headers=h,
                           json={"name": "Science FB1"}).json()
    cs2 = client.post("/api/v1/academics/class-subjects", headers=h, json={
        "class_id": ctx["class"]["id"], "subject_id": subject2["id"],
        "periods_per_week": 1, "teacher_member_id": ctx["teacher_mid"]}).json()

    card = client.get("/api/v1/periods/card", headers=th, params={
        "class_id": ctx["class"]["id"], "period_no": 1,
        "class_subject_id": cs2["id"]}).json()
    assert card["class_subject_id"] == ctx["cs"]["id"], \
        "the timetable outranks a passed subject"


def test_a_holiday_briefing_says_holiday_not_exams(client, cleanup):
    """`FB-1a` regression on its own fix. A closure is `teaching_off` as much as
    an exam is, so the teaching line has to name which — "Exams — no timetabled
    lessons today" on Independence Day would be a new lie for an old one."""
    ctx = _setup(client, cleanup)
    h = ctx["h"]
    _timetable(client, h, ctx)

    _event(client, h, ctx, kind="holiday", title="Independence Day")

    teaching = _section(_briefing(client, h), "teaching")
    assert "Independence Day" in teaching, teaching
    assert "Exams" not in teaching
