"""HS-1: hostel sessions — computed multi-class rosters, teacher clash, homework
board, per-student study logs, media memories (local-fallback storage)."""

import io
import uuid

PW = "supersecret1"


def _setup(client, cleanup):
    """Org + year + two classes with students; class 6A has a Hosteller category."""
    email = f"admin-{uuid.uuid4().hex[:12]}@example.com"
    reg = client.post("/api/v1/auth/register-org",
                      json={"org_name": "Hostel Org", "name": "Director", "email": email,
                            "password": PW, "timezone": "Asia/Kolkata"}).json()
    cleanup["orgs"].append(uuid.UUID(reg["org"]["id"]))
    cleanup["users"].append(uuid.UUID(reg["user"]["id"]))
    h = {"Authorization": f"Bearer {reg['access_token']}"}
    year = client.post("/api/v1/academics/years", headers=h,
                       json={"label": "2026-27", "start_date": "2026-04-01",
                             "end_date": "2027-03-31"}).json()
    c6 = client.post("/api/v1/academics/classes", headers=h,
                     json={"academic_year_id": year["id"], "name": "6", "section": "A"}).json()
    c7 = client.post("/api/v1/academics/classes", headers=h,
                     json={"academic_year_id": year["id"], "name": "7", "section": "A"}).json()
    cats = client.post("/api/v1/students/categories/seed-defaults", headers=h).json()
    hosteller = next(c["id"] for c in cats if c["name"] == "Hosteller")
    day = next(c["id"] for c in cats if c["name"] == "Day Scholar")

    def add(name, klass, cat):
        return client.post("/api/v1/students", headers=h, json={
            "admission_no": f"S{uuid.uuid4().hex[:8]}", "full_name": name,
            "class_id": klass, "category_id": cat}).json()

    kids6 = [add("Asha H", c6["id"], hosteller), add("Bina H", c6["id"], hosteller),
             add("Chetan D", c6["id"], day)]
    kids7 = [add("Divya H", c7["id"], hosteller), add("Esha D", c7["id"], day)]
    return h, year, c6, c7, kids6, kids7, hosteller


def _teacher(client, h):
    """Create a teacher member; return (headers, member_id)."""
    username = f"t{uuid.uuid4().hex[:8]}"
    bulk = client.post("/api/v1/org/members/bulk", headers=h, json={"members": [
        {"username": username, "password": PW, "role": "teacher"}]})
    assert bulk.status_code == 200, bulk.text
    login = client.post("/api/v1/auth/login",
                        json={"identifier": username, "password": PW}).json()
    members = client.get("/api/v1/org/members", headers=h).json()["members"]
    member_id = next(m["member_id"] for m in members if m.get("username") == username)
    return {"Authorization": f"Bearer {login['access_token']}"}, member_id


def test_multiclass_roster_hosteller_filter_and_zero_touch_growth(client, cleanup):
    h, _y, c6, c7, kids6, kids7, hosteller = _setup(client, cleanup)

    created = client.post("/api/v1/sessions", headers=h, json={
        "name": "Evening prep", "kind": "study", "weekdays": [0, 1, 2, 3, 4],
        "time": "18:00", "end_time": "19:30",
        "class_ids": [c6["id"], c7["id"]], "hostellers_only": True})
    assert created.status_code == 200, created.text
    sess = created.json()
    # 3 hostellers across both classes; day scholars filtered out.
    assert sess["roster_count"] == 3
    names = {s["full_name"] for s in sess["students"]}
    assert names == {"Asha H", "Bina H", "Divya H"}
    assert sorted(sess["class_labels"]) == ["6A", "7A"]

    # Explicit ad-hoc addition of a day scholar joins the computed roster.
    upd = client.patch(f"/api/v1/sessions/{sess['id']}", headers=h,
                       json={"student_ids": [kids6[2]["id"]]})
    assert upd.status_code == 200, upd.text
    assert upd.json()["roster_count"] == 4
    chetan = next(s for s in upd.json()["students"] if s["full_name"] == "Chetan D")
    assert chetan["explicit"] is True

    # A newly admitted hosteller appears with zero session edits (computed roster).
    client.post("/api/v1/students", headers=h, json={
        "admission_no": f"S{uuid.uuid4().hex[:8]}", "full_name": "Farah H",
        "class_id": c7["id"], "category_id": hosteller})
    got = client.get(f"/api/v1/sessions/{sess['id']}", headers=h).json()
    assert got["roster_count"] == 5


def test_teacher_clash_is_deterministic(client, cleanup):
    h, *_ = _setup(client, cleanup)
    th, member_id = _teacher(client, h)

    ok = client.post("/api/v1/sessions", headers=h, json={
        "name": "Yoga", "kind": "activity", "weekdays": [0, 2], "time": "17:00",
        "end_time": "18:00", "owner_member_id": member_id})
    assert ok.status_code == 200, ok.text

    # Overlapping time on a shared weekday for the same teacher → conflict.
    clash = client.post("/api/v1/sessions", headers=h, json={
        "name": "Boxing", "kind": "activity", "weekdays": [2, 4], "time": "17:30",
        "end_time": "18:30", "owner_member_id": member_id})
    assert clash.status_code == 409, clash.text
    assert clash.json()["error"]["code"] == "teacher_clash"

    # Same time, different days → fine.
    fine = client.post("/api/v1/sessions", headers=h, json={
        "name": "Boxing", "kind": "activity", "weekdays": [1, 3], "time": "17:30",
        "end_time": "18:30", "owner_member_id": member_id})
    assert fine.status_code == 200, fine.text

    # Only an admin may assign someone else's session.
    denied = client.post("/api/v1/sessions", headers=th, json={
        "name": "Sneaky", "weekdays": [5], "time": "10:00", "owner_member_id": member_id})
    assert denied.status_code == 200  # assigning to *yourself* is fine
    other = client.post("/api/v1/sessions", headers=th, json={
        "name": "Sneakier", "weekdays": [5], "time": "11:00",
        "owner_member_id": str(uuid.uuid4())})
    assert other.status_code == 403


def test_homework_board_joins_class_and_personal_rows(client, cleanup):
    h, _y, c6, _c7, kids6, _kids7, _hos = _setup(client, cleanup)
    subj = client.post("/api/v1/academics/subjects", headers=h, json={"name": "Maths"}).json()
    cs = client.post("/api/v1/academics/class-subjects", headers=h, json={
        "class_id": c6["id"], "subject_id": subj["id"], "periods_per_week": 5}).json()

    client.post("/api/v1/classroom/homework", headers=h, json={
        "class_subject_id": cs["id"], "text": "Ex 4.2 Q1–Q10"})
    client.post("/api/v1/classroom/homework", headers=h, json={
        "class_subject_id": cs["id"], "text": "Extra practice sheet",
        "student_id": kids6[0]["id"]})

    sess = client.post("/api/v1/sessions", headers=h, json={
        "name": "Homework hall", "kind": "homework", "weekdays": list(range(6)),
        "time": "19:00", "class_ids": [c6["id"]]}).json()
    meeting = client.post(f"/api/v1/sessions/{sess['id']}/meetings", headers=h).json()
    assert meeting["kind"] == "homework"

    board = client.get(f"/api/v1/sessions/meetings/{meeting['id']}/homework", headers=h)
    assert board.status_code == 200, board.text
    rows = {r["full_name"]: r for r in board.json()["rows"]}
    # Asha: class-wide + her personal item; Bina: class-wide only.
    asha = rows["Asha H"]
    assert {i["text"] for i in asha["items"]} == {"Ex 4.2 Q1–Q10", "Extra practice sheet"}
    assert any(i["personal"] for i in asha["items"])
    assert {i["text"] for i in rows["Bina H"]["items"]} == {"Ex 4.2 Q1–Q10"}
    assert rows["Bina H"]["items"][0]["subject"] == "Maths"


def test_student_card_sectioned_logs_and_timeline(client, cleanup):
    h, _y, c6, _c7, kids6, _kids7, _hos = _setup(client, cleanup)
    subj = client.post("/api/v1/academics/subjects", headers=h, json={"name": "Maths"}).json()
    cs = client.post("/api/v1/academics/class-subjects", headers=h, json={
        "class_id": c6["id"], "subject_id": subj["id"], "periods_per_week": 5}).json()
    client.post("/api/v1/classroom/homework", headers=h, json={
        "class_subject_id": cs["id"], "text": "Ex 4.2 Q1–Q10"})
    sess = client.post("/api/v1/sessions", headers=h, json={
        "name": "Evening prep", "kind": "study", "weekdays": list(range(6)),
        "time": "18:00", "class_ids": [c6["id"]]}).json()
    meeting = client.post(f"/api/v1/sessions/{sess['id']}/meetings", headers=h).json()
    asha, bina = kids6[0], kids6[1]
    base = f"/api/v1/sessions/meetings/{meeting['id']}/students/{asha['id']}"

    # Attendance first (the ≤60s flow) — logs are an optional enrichment.
    client.patch(f"/api/v1/sessions/meetings/{meeting['id']}/attendance", headers=h, json={
        "rows": [{"student_id": asha["id"], "status": "present"},
                 {"student_id": bina["id"], "status": "present"}]})

    # Sectioned log, full-replace per student (like the class deep log).
    r = client.put(f"{base}/logs", headers=h, json={"entries": [
        {"section": "Maths", "note": "Finished Ex 4.2"},
        {"section": "Science", "note": "Revised diagrams"}]})
    assert r.status_code == 200, r.text
    card = r.json()
    assert [e["section"] for e in card["logs"]] == ["Maths", "Science"]
    # The card is the student page's single round trip: homework rides along.
    assert card["homework"][0]["text"] == "Ex 4.2 Q1–Q10"
    assert card["status"] == "present"

    # Bina has no rows — never mandatory (P1v2).
    other = client.get(
        f"/api/v1/sessions/meetings/{meeting['id']}/students/{bina['id']}", headers=h).json()
    assert other["logs"] == []

    # Replace shrinks; the meeting roster carries count + preview.
    r = client.put(f"{base}/logs", headers=h, json={"entries": [
        {"section": "Maths", "note": "Maths only"}]})
    assert [e["note"] for e in r.json()["logs"]] == ["Maths only"]
    roster = {row["student_id"]: row for row in client.post(
        f"/api/v1/sessions/{sess['id']}/meetings", headers=h).json()["roster"]}
    assert roster[asha["id"]]["log_count"] == 1
    assert roster[asha["id"]]["log_note"] == "Maths: Maths only"

    # The sections land in the student's day timeline, folded into one line.
    tl = client.get(f"/api/v1/students/{asha['id']}/timeline", headers=h)
    assert tl.status_code == 200, tl.text
    sessions = tl.json()["sessions"]
    assert len(sessions) == 1
    assert sessions[0]["kind"] == "study" and sessions[0]["log_note"] == "Maths: Maths only"


def test_media_memories_local_fallback(client, cleanup):
    h, _y, c6, _c7, _kids6, _kids7, _hos = _setup(client, cleanup)
    sess = client.post("/api/v1/sessions", headers=h, json={
        "name": "Yoga", "kind": "activity", "weekdays": [5], "time": "06:30",
        "class_ids": [c6["id"]]}).json()
    meeting = client.post(f"/api/v1/sessions/{sess['id']}/meetings", headers=h).json()
    mid = meeting["id"]

    # Direct upload (dev fallback path — no R2 configured in tests).
    up = client.post(f"/api/v1/sessions/meetings/{mid}/media",
                     files={"file": ("stretch.jpg", io.BytesIO(b"jpegbytes"), "image/jpeg")},
                     data={"caption": "Morning stretch"}, headers=h)
    assert up.status_code == 200, up.text
    media = up.json()["media"]
    assert len(media) == 1 and media[0]["kind"] == "photo"
    assert media[0]["caption"] == "Morning stretch" and media[0]["url"]

    # Presign without R2 → key minted, no upload_url (client falls back to direct).
    pre = client.post(f"/api/v1/sessions/meetings/{mid}/media/presign", headers=h, json={
        "filename": "match.mp4", "content_type": "video/mp4", "size_bytes": 1024})
    assert pre.status_code == 200, pre.text
    assert pre.json()["upload_url"] is None
    assert pre.json()["key"].endswith(".mp4")

    # Confirming a key that was never uploaded fails cleanly.
    bad = client.post(f"/api/v1/sessions/meetings/{mid}/media/confirm", headers=h,
                      json={"key": pre.json()["key"]})
    assert bad.status_code == 422
    assert bad.json()["error"]["code"] == "media_not_uploaded"

    # Non-media content types are rejected.
    doc = client.post(f"/api/v1/sessions/meetings/{mid}/media",
                      files={"file": ("h.pdf", io.BytesIO(b"%PDF"), "application/pdf")}, headers=h)
    assert doc.status_code == 422

    # Per-student memory (HS-2): tagged media leaves the class strip and shows
    # on the student's card instead.
    kid = client.get(f"/api/v1/sessions/{sess['id']}", headers=h).json()["students"][0]
    tagged = client.post(f"/api/v1/sessions/meetings/{mid}/media",
                         files={"file": ("pose.jpg", io.BytesIO(b"jpegbytes"), "image/jpeg")},
                         data={"student_id": kid["student_id"]}, headers=h)
    assert tagged.status_code == 200, tagged.text
    assert len(tagged.json()["media"]) == 1  # class strip unchanged
    card = client.get(f"/api/v1/sessions/meetings/{mid}/students/{kid['student_id']}",
                      headers=h).json()
    assert len(card["media"]) == 1 and card["media"][0]["student_id"] == kid["student_id"]

    # Delete removes the row.
    gone = client.delete(f"/api/v1/sessions/media/{media[0]['id']}", headers=h)
    assert gone.status_code == 200
    again = client.post(f"/api/v1/sessions/{sess['id']}/meetings", headers=h).json()
    assert again["media"] == []


def test_admin_plans_teacher_runs_others_blocked(client, cleanup):
    h, _y, c6, _c7, _kids6, _kids7, _hos = _setup(client, cleanup)
    th, member_id = _teacher(client, h)
    oth, _ = _teacher(client, h)

    sess = client.post("/api/v1/sessions", headers=h, json={
        "name": "Homework hall", "kind": "homework", "weekdays": [0], "time": "19:00",
        "class_ids": [c6["id"]], "owner_member_id": member_id}).json()
    assert sess["teacher_name"]

    # The assigned teacher sees and runs it.
    mine = client.get("/api/v1/sessions", headers=th).json()
    assert [s["id"] for s in mine] == [sess["id"]]
    meeting = client.post(f"/api/v1/sessions/{sess['id']}/meetings", headers=th)
    assert meeting.status_code == 200

    # Another teacher can't touch it.
    assert client.get("/api/v1/sessions", headers=oth).json() == []
    blocked = client.post(f"/api/v1/sessions/{sess['id']}/meetings", headers=oth)
    assert blocked.status_code == 403
    blocked = client.get(f"/api/v1/sessions/meetings/{meeting.json()['id']}/homework", headers=oth)
    assert blocked.status_code == 403
