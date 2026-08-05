"""The staff directory (founder, 2026-08-05).

What each test defends — every one of them is a way the screen would start
lying, or a way the class-teacher fact would fork into two stores:

  * a row carries the assignments the org role cannot express: the homeroom, the
    classes they teach a subject in, and the weekly load, joined server-side so
    the table cannot compute a different total from the detail page;
  * `role_key` is DERIVED. There is no `class_teacher` value in `org_role`, and
    assigning a homeroom must change `school_classes` and nothing else — if a
    role column ever starts carrying it, the two will disagree the first time a
    class is reassigned;
  * `class_teacher_of` is a full replace, so un-assigning is expressible;
  * handing a class to a second teacher REPLACES the first — a homeroom has one
    owner, and a silent refusal would leave the admin unable to hand it over;
  * the last admin cannot be demoted through this door either (the guard lives in
    `MemberService.change_role`, and this proves the directory goes through it);
  * a teacher can read their own file and gets a 403 on a colleague's;
  * the directory list itself is admin-only.
"""

import uuid

from sqlalchemy import select

from app.models import Membership, SchoolClass
from tests.conftest import AdminSession
from tests.test_staff import _membership_id


def _setup(client, cleanup):
    email = f"admin-{uuid.uuid4().hex[:12]}@example.com"
    reg = client.post("/api/v1/auth/register-org",
                      json={"org_name": "Directory Org", "name": "Director", "email": email,
                            "password": "supersecret1", "timezone": "Asia/Kolkata"}).json()
    cleanup["orgs"].append(uuid.UUID(reg["org"]["id"]))
    cleanup["users"].append(uuid.UUID(reg["user"]["id"]))
    h = {"Authorization": f"Bearer {reg['access_token']}"}

    year = client.post("/api/v1/academics/years", headers=h,
                       json={"label": "2026-27", "start_date": "2026-04-01",
                             "end_date": "2027-03-31"}).json()
    six_a = client.post("/api/v1/academics/classes", headers=h,
                        json={"academic_year_id": year["id"], "name": "6",
                              "section": "A"}).json()
    six_b = client.post("/api/v1/academics/classes", headers=h,
                        json={"academic_year_id": year["id"], "name": "6",
                              "section": "B"}).json()
    maths = client.post("/api/v1/academics/subjects", headers=h,
                        json={"name": "Mathematics"}).json()

    bulk = client.post("/api/v1/org/members/bulk", headers=h, json={"members": [
        {"name": "Ramesh Kumar", "username": f"r{uuid.uuid4().hex[:8]}",
         "password": "supersecret1", "role": "teacher"},
        {"name": "Anil Sharma", "username": f"a{uuid.uuid4().hex[:8]}",
         "password": "supersecret1", "role": "teacher"},
    ]}).json()["results"]
    for row in bulk:
        cleanup["users"].append(uuid.UUID(row["user_id"]))
    ramesh_mid = str(_membership_id(bulk[0]["user_id"], reg["org"]["id"]))
    anil_mid = str(_membership_id(bulk[1]["user_id"], reg["org"]["id"]))

    client.post("/api/v1/academics/class-subjects", headers=h,
                json={"class_id": six_a["id"], "subject_id": maths["id"],
                      "teacher_member_id": ramesh_mid, "periods_per_week": 6})

    login = client.post("/api/v1/auth/login",
                        json={"identifier": bulk[0]["username"],
                              "password": "supersecret1"}).json()
    th = {"Authorization": f"Bearer {login['access_token']}"}
    return {
        "h": h, "th": th, "year": year, "six_a": six_a, "six_b": six_b,
        "ramesh": bulk[0], "ramesh_mid": ramesh_mid, "anil_mid": anil_mid,
        "admin_user_id": reg["user"]["id"], "org_id": reg["org"]["id"],
    }


def _row(board, member_id):
    return next(r for r in board["rows"] if r["member_id"] == member_id)


def test_row_carries_the_assignments_the_role_cannot_express(client, cleanup):
    ctx = _setup(client, cleanup)
    board = client.get("/api/v1/staff/directory", headers=ctx["h"]).json()

    ramesh = _row(board, ctx["ramesh_mid"])
    assert ramesh["org_role"] == "teacher"
    assert ramesh["role_key"] == "teacher"      # no homeroom yet
    assert ramesh["subject_count"] == 1
    assert ramesh["periods_per_week"] == 6
    assert [c["class_label"] for c in ramesh["classes"]] == ["6-A"]
    assert ramesh["subjects"][0]["subject_name"] == "Mathematics"

    # Anil teaches nothing — an empty load is a fact the screen must be able to
    # show, not a row that quietly goes missing.
    anil = _row(board, ctx["anil_mid"])
    assert anil["subject_count"] == 0 and anil["classes"] == []

    # Both classes have no class teacher, and the header is told so.
    assert {c["class_label"] for c in board["classes_without_teacher"]} == {"6-A", "6-B"}
    assert board["class_teachers"] == 0
    assert board["teachers"] == 2 and board["admins"] == 1


def test_class_teacher_is_derived_and_stored_only_on_the_class(client, cleanup):
    """The founder's call, made structural. Picking "Class teacher" in the Role
    dropdown must write `school_classes.class_teacher_member_id` and leave
    `org_role` alone — a `class_teacher` value in the role column would be the
    same fact in two places, and they would disagree on the first reassignment."""
    ctx = _setup(client, cleanup)
    res = client.patch(f"/api/v1/staff/directory/{ctx['ramesh_mid']}", headers=ctx["h"],
                       json={"class_teacher_of": [ctx["six_a"]["id"]]})
    assert res.status_code == 200
    row = res.json()["row"]

    assert row["role_key"] == "class_teacher"
    assert row["role_label"] == "Class teacher · 6-A"
    # ...and the STORED role is untouched.
    assert row["org_role"] == "teacher"

    db = AdminSession()
    try:
        mem = db.scalar(select(Membership).where(
            Membership.id == uuid.UUID(ctx["ramesh_mid"])))
        assert mem.org_role == "teacher", "the role column must not carry the homeroom"
        klass = db.scalar(select(SchoolClass).where(
            SchoolClass.id == uuid.UUID(ctx["six_a"]["id"])))
        assert str(klass.class_teacher_member_id) == ctx["ramesh_mid"]
    finally:
        db.close()

    # The nav's own signal, which reads the same column, agrees.
    me = client.get("/api/v1/auth/me", headers=ctx["th"]).json()
    assert me["is_class_teacher"] is True


def test_homeroom_set_is_a_full_replace(client, cleanup):
    """`[]` must mean "class teacher of nothing" — the same shape as marking
    attendance. Without it there is no way to un-assign somebody."""
    ctx = _setup(client, cleanup)
    h = ctx["h"]
    client.patch(f"/api/v1/staff/directory/{ctx['ramesh_mid']}", headers=h,
                 json={"class_teacher_of": [ctx["six_a"]["id"], ctx["six_b"]["id"]]})
    row = client.get(f"/api/v1/staff/directory/{ctx['ramesh_mid']}",
                     headers=h).json()["row"]
    assert {c["class_label"] for c in row["class_teacher_of"]} == {"6-A", "6-B"}

    client.patch(f"/api/v1/staff/directory/{ctx['ramesh_mid']}", headers=h,
                 json={"class_teacher_of": [ctx["six_b"]["id"]]})
    row = client.get(f"/api/v1/staff/directory/{ctx['ramesh_mid']}",
                     headers=h).json()["row"]
    assert [c["class_label"] for c in row["class_teacher_of"]] == ["6-B"]

    client.patch(f"/api/v1/staff/directory/{ctx['ramesh_mid']}", headers=h,
                 json={"class_teacher_of": []})
    row = client.get(f"/api/v1/staff/directory/{ctx['ramesh_mid']}",
                     headers=h).json()["row"]
    assert row["class_teacher_of"] == [] and row["role_key"] == "teacher"


def test_handing_a_homeroom_over_replaces_the_previous_owner(client, cleanup):
    """A class has exactly one class teacher. Refusing here would leave the admin
    unable to hand 6-A over without first knowing to go and unassign Ramesh."""
    ctx = _setup(client, cleanup)
    h = ctx["h"]
    client.patch(f"/api/v1/staff/directory/{ctx['ramesh_mid']}", headers=h,
                 json={"class_teacher_of": [ctx["six_a"]["id"]]})
    client.patch(f"/api/v1/staff/directory/{ctx['anil_mid']}", headers=h,
                 json={"class_teacher_of": [ctx["six_a"]["id"]]})

    board = client.get("/api/v1/staff/directory", headers=h).json()
    assert _row(board, ctx["anil_mid"])["role_key"] == "class_teacher"
    assert _row(board, ctx["ramesh_mid"])["class_teacher_of"] == []
    assert board["class_teachers"] == 1


def test_role_change_goes_through_the_last_admin_guard(client, cleanup):
    """The directory must not be a second path to `org_role` — the last-admin
    refusal and the token_version bump live in `MemberService.change_role`."""
    ctx = _setup(client, cleanup)
    h = ctx["h"]
    admin_mid = str(_membership_id(ctx["admin_user_id"], ctx["org_id"]))

    res = client.patch(f"/api/v1/staff/directory/{admin_mid}", headers=h,
                       json={"org_role": "teacher"})
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "last_admin"

    # Promoting a teacher is fine, and the row re-reads as an admin.
    res = client.patch(f"/api/v1/staff/directory/{ctx['anil_mid']}", headers=h,
                       json={"org_role": "admin"})
    assert res.status_code == 200
    assert res.json()["row"]["role_key"] == "admin"


def test_profile_edits_and_duplicate_contact_is_refused(client, cleanup):
    ctx = _setup(client, cleanup)
    h = ctx["h"]
    res = client.patch(f"/api/v1/staff/directory/{ctx['ramesh_mid']}", headers=h,
                       json={"name": "Ramesh K. Kumar", "phone": "+919000000001",
                             "date_of_birth": "1988-04-12"})
    assert res.status_code == 200
    row = res.json()["row"]
    assert row["name"] == "Ramesh K. Kumar"
    assert row["phone"] == "+919000000001"
    assert row["date_of_birth"] == "1988-04-12"

    # The same number on a colleague is a conflict, not a silent overwrite —
    # `users.phone` is globally unique and it is the guardian/OTP key.
    res = client.patch(f"/api/v1/staff/directory/{ctx['anil_mid']}", headers=h,
                       json={"phone": "+919000000001"})
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "phone_taken"

    # Clearing needs its own flag — an absent field means "leave it alone".
    res = client.patch(f"/api/v1/staff/directory/{ctx['ramesh_mid']}", headers=h,
                       json={"clear_phone": True})
    assert res.json()["row"]["phone"] is None


def test_a_teacher_reads_only_her_own_file(client, cleanup):
    ctx = _setup(client, cleanup)
    th = ctx["th"]
    assert client.get("/api/v1/staff/directory", headers=th).status_code == 403
    mine = client.get(f"/api/v1/staff/directory/{ctx['ramesh_mid']}", headers=th)
    assert mine.status_code == 200
    assert mine.json()["can_edit"] is False

    theirs = client.get(f"/api/v1/staff/directory/{ctx['anil_mid']}", headers=th)
    assert theirs.status_code == 403
    assert theirs.json()["error"]["code"] == "not_your_record"

    # And she cannot write anyone's, including her own.
    assert client.patch(f"/api/v1/staff/directory/{ctx['ramesh_mid']}", headers=th,
                        json={"name": "Hacked"}).status_code == 403
