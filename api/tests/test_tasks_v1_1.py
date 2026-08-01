"""V1-1 — Tasks & the action rail (D-41/D-43/D-44/D-45/D-46/D-47, S-106).

What each test is defending — the claims that would be plausible but wrong if
the code drifted:

  * a rail follow-up CARRIES its subject and the row resolves the student's
    name — a title string alone cannot feed the timeline or the dedupe (D-46);
  * completion records "what happened?" on the event chain, the instance cache
    mirrors it, and reopen clears only the cache (D-46, law 3);
  * the rail dedupes on the OPEN task by subject — the second press extends,
    never twins — and the subject key works with no action-log history (D-47);
  * the board windows done rows to 7 days, REPORTS what it hid, and the date
    filter reaches everything older (D-44 — the filter ships with the window);
  * an open row nobody touched for 3 weeks is flagged stale, never auto-closed
    (D-45);
  * My Day shows rail follow-ups for 3 WORKING days (a Friday follow-up
    survives the weekend) plus anything due today, capped, with an honest
    older-count (D-41/D-43);
  * the student's timeline shows the follow-up raised about them (D-46).
"""

import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import update

from app.models import TaskEvent, TaskInstance
from tests.conftest import AdminSession


def _org(client, cleanup, tz="Asia/Kolkata"):
    email = f"admin-{uuid.uuid4().hex[:12]}@example.com"
    reg = client.post("/api/v1/auth/register-org",
                      json={"org_name": "Tasks Org", "name": "Director", "email": email,
                            "password": "supersecret1", "timezone": tz}).json()
    cleanup["orgs"].append(uuid.UUID(reg["org"]["id"]))
    cleanup["users"].append(uuid.UUID(reg["user"]["id"]))
    h = {"Authorization": f"Bearer {reg['access_token']}"}
    return h, reg


def _student(client, h, name="Kabir Shah"):
    return client.post("/api/v1/students", headers=h,
                       json={"admission_no": f"A{uuid.uuid4().hex[:6]}",
                             "full_name": name}).json()


def _board(client, h, name="Ops"):
    return client.post("/api/v1/boards", headers=h, json={"name": name}).json()


def _backdate_task(task_id: str, days: int) -> None:
    """Shift a task's created_at AND its events back `days` days — the only way
    to test time windows without waiting three weeks."""
    then = datetime.now(UTC) - timedelta(days=days)
    db = AdminSession()
    try:
        db.execute(update(TaskInstance).where(TaskInstance.id == uuid.UUID(task_id))
                   .values(created_at=then))
        db.execute(update(TaskEvent).where(TaskEvent.instance_id == uuid.UUID(task_id))
                   .values(created_at=then))
        db.commit()
    finally:
        db.close()


def _backdate_completion(task_id: str, days: int) -> None:
    then = datetime.now(UTC) - timedelta(days=days)
    db = AdminSession()
    try:
        db.execute(update(TaskInstance).where(TaskInstance.id == uuid.UUID(task_id))
                   .values(completed_at=then))
        db.commit()
    finally:
        db.close()


# ── D-46: subject + outcome ──────────────────────────────────────────────────
def test_followup_carries_subject_and_completion_records_outcome(client, cleanup):
    h, _ = _org(client, cleanup)
    student = _student(client, h)

    res = client.post("/api/v1/insights/actions/followup_assigned", headers=h,
                      json={"student_id": student["id"]}).json()
    task_id = res["task_id"]

    detail = client.get(f"/api/v1/tasks/{task_id}", headers=h).json()
    assert detail["subject"] is not None, "the rail must set what the task is about"
    assert detail["subject"]["type"] == "student"
    assert detail["subject"]["id"] == student["id"]
    assert detail["subject"]["name"] == "Kabir Shah"
    assert detail["outcome"] is None

    done = client.post(f"/api/v1/tasks/{task_id}/complete", headers=h,
                       json={"outcome": "Spoke to the father — fever, back Monday"})
    assert done.status_code == 200

    detail = client.get(f"/api/v1/tasks/{task_id}", headers=h).json()
    assert detail["outcome"] == "Spoke to the father — fever, back Monday"
    completed = [e for e in detail["events"] if e["type"] == "completed"]
    assert "fever" in completed[-1]["text"], "the outcome lives on the event chain"

    # Reopen clears the CACHE — the event keeps its payload (law 3).
    client.post(f"/api/v1/tasks/{task_id}/reopen", headers=h)
    detail = client.get(f"/api/v1/tasks/{task_id}", headers=h).json()
    assert detail["outcome"] is None
    assert any("fever" in e["text"] for e in detail["events"])


def test_task_subject_must_be_in_the_same_org(client, cleanup):
    h, _ = _org(client, cleanup)
    h2, _ = _org(client, cleanup)
    other_student = _student(client, h2, name="Other School")
    board = _board(client, h)
    res = client.post("/api/v1/tasks", headers=h, json={
        "board_id": board["id"], "title": "Cross-org probe",
        "subject_type": "student", "subject_id": other_student["id"]})
    assert res.status_code == 404


# ── D-47: dedupe keys on the subject, not the action log ─────────────────────
def test_dedupe_finds_the_open_task_by_subject_alone(client, cleanup):
    """A manually created open task ABOUT the student (subject set, no
    followup_actions history at all) must still absorb the rail's press."""
    h, _ = _org(client, cleanup)
    student = _student(client, h)
    board = _board(client, h, name="Follow-ups")
    manual = client.post("/api/v1/tasks", headers=h, json={
        "board_id": board["id"], "title": "Call Kabir Shah's parent",
        "subject_type": "student", "subject_id": student["id"]}).json()

    res = client.post("/api/v1/insights/actions/followup_assigned", headers=h,
                      json={"student_id": student["id"]}).json()
    assert res["already_done"] is True
    assert res["task_id"] == manual["id"], "subject key, not the rail's own log"


# ── D-44: the board windows its read and reports what it hid ─────────────────
def test_board_table_windows_done_and_the_date_filter_reaches_older(client, cleanup):
    h, _ = _org(client, cleanup)
    board = _board(client, h)

    fresh = client.post("/api/v1/tasks", headers=h,
                        json={"board_id": board["id"], "title": "Fresh"}).json()
    old = client.post("/api/v1/tasks", headers=h,
                      json={"board_id": board["id"], "title": "October follow-up"}).json()
    still_open = client.post("/api/v1/tasks", headers=h,
                             json={"board_id": board["id"], "title": "Open forever"}).json()
    client.post(f"/api/v1/tasks/{fresh['id']}/complete", headers=h)
    client.post(f"/api/v1/tasks/{old['id']}/complete", headers=h)
    _backdate_completion(old["id"], days=40)
    _backdate_task(still_open["id"], days=100)

    table = client.get(f"/api/v1/boards/{board['id']}/table", headers=h).json()
    titles = {r["title"] for r in table["rows"]}
    assert "Fresh" in titles, "done this week stays"
    assert "October follow-up" not in titles, "done 40 days ago leaves the default read"
    assert "Open forever" in titles, "open rows NEVER leave, whatever their age"
    assert table["hidden_done_count"] == 1, "the window must say what it hid"

    # The date filter ships with the window (D-44) — it reaches October.
    frm = (date.today() - timedelta(days=60)).isoformat()
    to = (date.today() - timedelta(days=30)).isoformat()
    filtered = client.get(
        f"/api/v1/boards/{board['id']}/table?done_from={frm}&done_to={to}",
        headers=h).json()
    titles = {r["title"] for r in filtered["rows"]}
    assert "October follow-up" in titles
    assert "Open forever" in titles, "open rows ride along under any filter"


# ── D-45: stale is a flag, never an auto-close ───────────────────────────────
def test_untouched_open_rows_are_flagged_stale_and_stay_open(client, cleanup):
    h, _ = _org(client, cleanup)
    board = _board(client, h)
    stale = client.post("/api/v1/tasks", headers=h,
                        json={"board_id": board["id"], "title": "Forgotten"}).json()
    fresh = client.post("/api/v1/tasks", headers=h,
                        json={"board_id": board["id"], "title": "New"}).json()
    _backdate_task(stale["id"], days=25)

    table = client.get(f"/api/v1/boards/{board['id']}/table", headers=h).json()
    by_title = {r["title"]: r for r in table["rows"]}
    assert by_title["Forgotten"]["stale"] is True
    assert by_title["Forgotten"]["status"] == "open", "stale is a state, not a close"
    assert by_title["New"]["stale"] is False
    assert fresh["id"] == by_title["New"]["id"]


# ── D-41/D-43: the My Day window ─────────────────────────────────────────────
def test_my_day_window_counts_working_days_and_reports_older(client, cleanup):
    """A rail follow-up from 2 working days back is shown even when the calendar
    gap is longer (weekend in between); a follow-up past the window drops out
    but is COUNTED, and a task due today appears whatever board it came from."""
    h, reg = _org(client, cleanup)
    student = _student(client, h)

    # Rail follow-up (defaults to the admin caller when the student has no
    # class teacher — assignee falls back unassigned; assign explicitly).
    rail = client.post("/api/v1/insights/actions/followup_assigned", headers=h,
                       json={"student_id": student["id"],
                             "user_id": reg["user"]["id"]}).json()
    # Backdate it 2 working days (Mon–Sat default week): pick the calendar-day
    # shift that spans exactly 2 working days back from today.
    d, working = date.today(), 0
    while True:
        d -= timedelta(days=1)
        if d.weekday() < 6:
            working += 1
        if working == 2:
            break
    _backdate_task(rail["task_id"], days=(date.today() - d).days)

    # An old follow-up outside the window: out of sight, inside the count.
    student2 = _student(client, h, name="Meera Iyer")
    old = client.post("/api/v1/insights/actions/followup_assigned", headers=h,
                      json={"student_id": student2["id"],
                            "user_id": reg["user"]["id"]}).json()
    _backdate_task(old["task_id"], days=15)

    # Due today on an unrelated board (the org's seeded default board — the
    # free plan caps boards at 2 and the rail's Follow-ups board is the second).
    boards = client.get("/api/v1/boards", headers=h).json()
    other_board = next(b for b in boards["my_boards"] if b["name"] != "Follow-ups")
    due = client.post("/api/v1/tasks", headers=h, json={
        "board_id": other_board["id"], "title": "Send the circular",
        "assignee_id": reg["user"]["id"],
        "due_at": datetime.now(UTC).isoformat()}).json()

    my_day = client.get("/api/v1/classroom/my-day", headers=h).json()
    ids = {t["id"] for t in my_day["tasks"]}
    assert rail["task_id"] in ids, "2 working days back is inside the window"
    assert due["id"] in ids, "due today rides in from any board"
    assert old["task_id"] not in ids, "day 15 has left My Day (it lives on /tasks)"
    assert my_day["older_task_count"] >= 1, "the window must never be silent"


# ── D-46: the student's timeline shows the follow-up ─────────────────────────
def test_timeline_shows_followup_raised_about_the_student(client, cleanup):
    h, _ = _org(client, cleanup)
    student = _student(client, h)
    res = client.post("/api/v1/insights/actions/followup_assigned", headers=h,
                      json={"student_id": student["id"]}).json()

    tl = client.get(f"/api/v1/students/{student['id']}/timeline", headers=h).json()
    assert len(tl["followups"]) == 1
    assert tl["followups"][0]["task_id"] == res["task_id"]
    assert tl["followups"][0]["status"] == "open"

    client.post(f"/api/v1/tasks/{res['task_id']}/complete", headers=h,
                json={"outcome": "Father called back"})
    tl = client.get(f"/api/v1/students/{student['id']}/timeline", headers=h).json()
    assert tl["followups"][0]["status"] == "done"
    assert tl["followups"][0]["outcome"] == "Father called back"
