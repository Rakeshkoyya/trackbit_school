"""The class teacher may take her own class's register — even with no subjects.

The founder's report, 2026-08-18: the class teacher of 11-A and 12-A tapped
"take attendance" and the screen sat on *Loading roster…* forever. Prod showed
why — those two classes have **no `class_subjects` at all** (the school is mid
setup and their subjects and timetable were never mapped), and
`assert_can_take_class` only ever asked two questions: does she teach a subject
in this class, and is she covering it as a substitute today. The class teacher
of a class with no subjects answered no to both and got a 403.

The hole was bigger than one screen. `visible_class_ids` has read *the subjects
she teaches ∪ the homeroom she owns* since 2026-08-05, so her class appeared on
the attendance board, in My Day and in the exam feed — and then every one of
those screens refused her the instant she tapped it. The board offering a class
the sheet then denies is the worst of both: it is not a permission the school
intended to withhold, it is two functions disagreeing about the same rule.

What this suite pins:

  * the class teacher opens the roster of a class she teaches NO subject in,
    and marks it — the exact prod shape (zero `class_subjects` on the class);
  * she still gets in when the class HAS subjects, all taught by other people
    (7-B on prod: six subjects, none hers);
  * the board and the sheet agree — every class `my-classes` offers her can
    actually be opened, which is the invariant that was broken;
  * a teacher who is neither the class teacher nor a subject teacher is still
    refused. Widening the rule to the homeroom must not widen it to everyone.
"""

import uuid

import pytest

from tests.test_insights import _setup, _teacher


def _roster(client, headers, class_id, period_no=1):
    return client.get(
        f"/api/v1/attendance/roster?class_id={class_id}&period_no={period_no}",
        headers=headers)


def _make_class(client, h, ctx, name, section, class_teacher_mid=None):
    body = {"academic_year_id": ctx["year"]["id"], "name": name, "section": section}
    if class_teacher_mid is not None:
        body["class_teacher_member_id"] = class_teacher_mid
    res = client.post("/api/v1/academics/classes", headers=h, json=body)
    assert res.status_code == 200, res.text
    return res.json()


def _add_student(client, h, class_id, full_name):
    res = client.post("/api/v1/students", headers=h, json={
        "admission_no": f"A{uuid.uuid4().hex[:6]}", "full_name": full_name,
        "class_id": class_id})
    assert res.status_code == 200, res.text
    return res.json()


@pytest.fixture
def bare_class(client, cleanup):
    """11-A as prod has it: a class teacher, students, and NO class_subjects.

    This is the whole bug in one fixture. Nothing here is exotic — it is what
    every class looks like between "the office typed in the children" and
    "somebody mapped the timetable", which on a live school can be weeks.
    """
    ctx = _setup(client, cleanup)
    h = ctx["h"]
    # A third teacher who takes nothing anywhere — 11-A's class teacher.
    ct_headers, ct_mid = _teacher(client, cleanup, h, ctx["org_id"])
    klass = _make_class(client, h, ctx, "11", "A", class_teacher_mid=ct_mid)
    students = [_add_student(client, h, klass["id"], n)
                for n in ("Meera Nair", "Rohit Sen")]
    return {**ctx, "ct": ct_headers, "ct_mid": ct_mid,
            "bare_class": klass, "bare_students": students}


def test_class_teacher_opens_a_class_with_no_subjects_mapped(client, bare_class):
    """The prod repro: 11-A has zero class_subjects and she is refused."""
    res = _roster(client, bare_class["ct"], bare_class["bare_class"]["id"])

    assert res.status_code == 200, (
        "the class teacher of a class whose subjects were never mapped must "
        f"still be able to take its register — got {res.text}")
    sheet = res.json()
    assert len(sheet["roster"]) == 2
    assert sheet["marked"] is False
    # Not-captured is a word, never a zero: an unopened register reports its
    # roll, and every child on it defaults to present until tapped.
    assert sheet["present_count"] == 2
    assert sheet["absent_count"] == 0


def test_class_teacher_can_mark_it_not_just_read_it(client, bare_class):
    """Opening the sheet is worthless if saving it 403s a second later."""
    klass = bare_class["bare_class"]
    absent = bare_class["bare_students"][0]["id"]

    res = client.post("/api/v1/attendance/mark", headers=bare_class["ct"], json={
        "class_id": klass["id"], "period_no": 1,
        # No `class_subject_id`: there is no subject to file it against, which
        # is exactly the case that must work.
        "exceptions": [{"student_id": absent, "status": "absent"}]})
    assert res.status_code == 200, res.text
    out = res.json()
    assert out["roster_count"] == 2
    assert out["absent_count"] == 1
    assert out["present_count"] == 1

    # And it reads back as marked.
    again = _roster(client, bare_class["ct"], klass["id"]).json()
    assert again["marked"] is True
    assert again["absent_count"] == 1


def test_class_teacher_gets_in_when_others_teach_all_the_subjects(client, cleanup):
    """7-B on prod: six subjects exist, none of them are the class teacher's."""
    ctx = _setup(client, cleanup)
    h = ctx["h"]
    ct_headers, ct_mid = _teacher(client, cleanup, h, ctx["org_id"])
    klass = _make_class(client, h, ctx, "7", "B", class_teacher_mid=ct_mid)
    _add_student(client, h, klass["id"], "Anil Das")
    # Its one subject belongs to somebody else entirely.
    client.post("/api/v1/academics/class-subjects", headers=h, json={
        "class_id": klass["id"], "subject_id": ctx["subject"]["id"],
        "teacher_member_id": ctx["teacher_mid"], "periods_per_week": 3})

    res = _roster(client, ct_headers, klass["id"])
    assert res.status_code == 200, res.text
    assert len(res.json()["roster"]) == 1


def test_the_board_and_the_sheet_agree(client, bare_class):
    """Every class the board offers her must actually open.

    This is the invariant the bug broke, and the reason it is worth a test of
    its own rather than trusting the three above: `my-classes` is built from
    `visible_class_ids` and the sheet from `assert_can_take_class`, and the two
    answered differently. Asserting the agreement catches the next drift
    whichever side moves.
    """
    board = client.get("/api/v1/attendance/my-classes", headers=bare_class["ct"])
    assert board.status_code == 200, board.text
    offered = [r["class_id"] for r in board.json()["classes"]]
    assert bare_class["bare_class"]["id"] in offered, "her own class must be listed"

    for class_id in offered:
        res = _roster(client, bare_class["ct"], class_id)
        assert res.status_code == 200, (
            f"the board offered {class_id} and the sheet refused it: {res.text}")


def test_an_unrelated_teacher_is_still_refused(client, bare_class):
    """Widening the rule to the homeroom must not widen it to everyone."""
    # `th2` teaches nothing in 11-A and is not its class teacher.
    res = _roster(client, bare_class["th2"], bare_class["bare_class"]["id"])
    assert res.status_code == 403, res.text
    assert res.json()["error"]["code"] == "not_your_class"


# ── the other half of the report: "[object Object]" ──────────────────────────
# The founder also saw a toast reading literally "[object Object]" while saving
# a lesson detail, and could not reproduce it. The cause was not in any one
# screen: `api-client.ts` built its ApiError message as
# `err?.message ?? data?.detail`, and FastAPI's response to a body that fails
# PYDANTIC validation — before a line of our code runs — puts a LIST of objects
# in `detail`. `new Error(list)` coerces with String(), which is exactly
# "[object Object]".
#
# The client now flattens that list into "field: message". These tests pin the
# shape it flattens, because the frontend has no test runner in this repo and
# an unnoticed change to this envelope would silently bring the unreadable
# toast back.


def _bad_log(client, headers, body):
    return client.post("/api/v1/classroom/lesson-logs", headers=headers, json=body)


def test_a_validation_error_is_a_list_of_objects_under_detail(client, bare_class):
    """The 422 envelope the web client must flatten, not stringify."""
    res = _bad_log(client, bare_class["ct"], {"coverage": "full"})  # no class_subject_id
    assert res.status_code == 422, res.text
    body = res.json()

    # Not our `{"error": {...}}` envelope — this one never reaches AppError.
    assert "error" not in body, (
        "if this ever becomes the structured envelope, the web client's "
        "readDetail() fallback is dead code and should be revisited")
    detail = body["detail"]
    assert isinstance(detail, list) and detail, detail
    first = detail[0]
    # The two keys `readDetail` reads. If either is renamed the toast silently
    # degrades to the generic fallback, which is the failure this pins.
    assert isinstance(first["msg"], str) and first["msg"]
    assert isinstance(first["loc"], list)
    # "body" leads the location and names our transport, not a field the person
    # can act on — the client strips it, leaving "class_subject_id".
    assert first["loc"][0] == "body"
    assert "class_subject_id" in first["loc"]


def test_a_business_error_still_uses_the_structured_envelope(client, bare_class):
    """The normal path is unchanged: `error.message` is a readable string.

    Worth asserting beside the 422 so the two envelopes stay visibly different.
    `readDetail` is only ever reached when `error.message` is absent.
    """
    res = _roster(client, bare_class["th2"], bare_class["bare_class"]["id"])
    assert res.status_code == 403
    err = res.json()["error"]
    assert isinstance(err["message"], str) and err["message"].strip()
    assert err["code"] == "not_your_class"
