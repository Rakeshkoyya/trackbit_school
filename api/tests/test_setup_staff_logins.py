"""Correcting the staff logins the pack import generated, before handover.

What each test defends:

  * the operator can **rename** a generated username and **choose** a password,
    which is the whole point — after handover the hash is all that exists;
  * `users.username` is **global**, so the availability check spans every school
    and the save refuses a name another school already holds;
  * a person's **own** username never reads as taken, or nobody could save a row
    they did not change;
  * the batch is **all or nothing** — a partial rename leaves half the staff
    holding logins from a handover sheet that is now wrong;
  * the **operator is not staff** (`core/staff.py::not_operator`): the vendor's
    own account is neither listed nor renameable through a school's setup;
  * only a **super-admin** reaches any of it.
"""

import uuid

from sqlalchemy import select

from app.core.security import verify_password
from app.models import Membership, User
from tests.conftest import AdminSession


def _register(client, cleanup, *, org="Login Test School"):
    email = f"op-{uuid.uuid4().hex[:12]}@example.com"
    reg = client.post("/api/v1/auth/register-org", json={
        "org_name": org, "name": "Operator", "email": email,
        "password": "supersecret1", "timezone": "Asia/Kolkata"}).json()
    cleanup["orgs"].append(uuid.UUID(reg["org"]["id"]))
    cleanup["users"].append(uuid.UUID(reg["user"]["id"]))
    return reg


def _promote(user_id: str) -> None:
    """The only way the flag is ever granted — there is deliberately no route."""
    db = AdminSession()
    try:
        db.get(User, uuid.UUID(user_id)).is_super_admin = True
        db.commit()
    finally:
        db.close()


def _operator(client, cleanup):
    """A super-admin, plus a school of their own to run setup against."""
    reg = _register(client, cleanup)
    _promote(reg["user"]["id"])
    return ({"Authorization": f"Bearer {reg['access_token']}"},
            reg["org"]["id"], reg["user"]["id"])


def _add_teacher(client, cleanup, h, name, phone):
    """An invited teacher stands in for an imported one: both end up as a User
    with a membership, which is all this screen edits."""
    inv = client.post("/api/v1/org/members/invite", headers=h,
                      json={"name": name, "phone": phone, "role": "teacher"}).json()
    cleanup["users"].append(uuid.UUID(inv["user_id"]))
    return inv["user_id"]


def _set_username(user_id: str, username: str) -> None:
    db = AdminSession()
    try:
        db.get(User, uuid.UUID(user_id)).username = username
        db.commit()
    finally:
        db.close()


def test_logins_list_excludes_the_operator(client, cleanup):
    h, org_id, operator_id = _operator(client, cleanup)
    teacher_id = _add_teacher(client, cleanup, h, "Asha Rao", "+919800000101")

    rows = client.get(f"/api/v1/platform/orgs/{org_id}/setup/logins", headers=h)
    assert rows.status_code == 200, rows.text
    ids = {r["user_id"] for r in rows.json()}
    assert teacher_id in ids
    # The operator is a member of every school they set up and is not its staff.
    assert operator_id not in ids


def test_rename_and_set_password(client, cleanup):
    h, org_id, _ = _operator(client, cleanup)
    teacher_id = _add_teacher(client, cleanup, h, "Asha Rao", "+919800000102")
    _set_username(teacher_id, f"asha.rao.{uuid.uuid4().hex[:6]}")

    wanted = f"emp.{uuid.uuid4().hex[:8]}"
    saved = client.post(f"/api/v1/platform/orgs/{org_id}/setup/logins", headers=h,
                        json={"logins": [{"user_id": teacher_id,
                                          "username": wanted,
                                          "password": "chosen-one-99"}]})
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert body["renamed"] == 1 and body["passwords_set"] == 1

    db = AdminSession()
    try:
        user = db.get(User, uuid.UUID(teacher_id))
        assert user.username == wanted
        assert verify_password("chosen-one-99", user.password_hash)
        # A chosen password is still a TEMP one — the teacher changes it at
        # first sign-in exactly as with a generated one.
        assert user.must_set_password is True
    finally:
        db.close()


def test_username_is_uppercased_down_and_own_name_is_free(client, cleanup):
    h, org_id, _ = _operator(client, cleanup)
    teacher_id = _add_teacher(client, cleanup, h, "Bilal Khan", "+919800000103")
    mine = f"bilal.{uuid.uuid4().hex[:8]}"
    _set_username(teacher_id, mine)

    # Checking somebody's own username must say "available" — otherwise no row
    # could be saved unless it was being changed.
    own = client.get("/api/v1/platform/username-check", headers=h,
                     params={"username": mine.upper(), "for_user_id": teacher_id})
    assert own.status_code == 200, own.text
    assert own.json()["available"] is True
    assert own.json()["username"] == mine, "normalised to lowercase"

    # ...and without `for_user_id` the same name is taken.
    anyone = client.get("/api/v1/platform/username-check", headers=h,
                        params={"username": mine})
    assert anyone.json()["available"] is False
    assert "taken" in (anyone.json()["reason"] or "").lower()


def test_username_shape_is_answered_not_errored(client, cleanup):
    h, _org_id, _ = _operator(client, cleanup)
    for bad, word in (("ab", "short"), ("asha rao", "only"), ("asha@rao", "only")):
        r = client.get("/api/v1/platform/username-check", headers=h,
                       params={"username": bad})
        assert r.status_code == 200, f"{bad} should answer, not error: {r.text}"
        assert r.json()["available"] is False
        assert word in (r.json()["reason"] or "").lower()


def test_a_name_another_school_holds_is_refused(client, cleanup):
    h_a, org_a, _ = _operator(client, cleanup)
    h_b, org_b, _ = _operator(client, cleanup)
    theirs = f"shared.{uuid.uuid4().hex[:8]}"
    other = _add_teacher(client, cleanup, h_b, "Other School Teacher", "+919800000104")
    _set_username(other, theirs)

    mine = _add_teacher(client, cleanup, h_a, "Chandra P", "+919800000105")
    clash = client.post(f"/api/v1/platform/orgs/{org_a}/setup/logins", headers=h_a,
                        json={"logins": [{"user_id": mine, "username": theirs}]})
    assert clash.status_code == 409, clash.text
    assert org_b  # the other school is untouched; named for the reader


def test_two_rows_cannot_claim_one_username(client, cleanup):
    h, org_id, _ = _operator(client, cleanup)
    one = _add_teacher(client, cleanup, h, "Deepa N", "+919800000106")
    two = _add_teacher(client, cleanup, h, "Esha M", "+919800000107")
    wanted = f"dup.{uuid.uuid4().hex[:8]}"

    r = client.post(f"/api/v1/platform/orgs/{org_id}/setup/logins", headers=h,
                    json={"logins": [{"user_id": one, "username": wanted},
                                     {"user_id": two, "username": wanted}]})
    assert r.status_code == 409, r.text


def test_a_refused_batch_saves_nothing(client, cleanup):
    """All or nothing: the first row is perfectly good, and must not survive the
    second row's clash — the operator prints one sheet for the whole school."""
    h, org_id, _ = _operator(client, cleanup)
    good = _add_teacher(client, cleanup, h, "Farida S", "+919800000108")
    bad = _add_teacher(client, cleanup, h, "Gopal V", "+919800000109")
    before = f"before.{uuid.uuid4().hex[:8]}"
    _set_username(good, before)

    r = client.post(f"/api/v1/platform/orgs/{org_id}/setup/logins", headers=h,
                    json={"logins": [
                        {"user_id": good, "username": f"after.{uuid.uuid4().hex[:8]}"},
                        {"user_id": bad, "username": "no"},  # too short
                    ]})
    assert r.status_code in (400, 422), r.text

    db = AdminSession()
    try:
        assert db.get(User, uuid.UUID(good)).username == before
    finally:
        db.close()


def test_a_user_from_another_school_is_not_reachable(client, cleanup):
    h_a, org_a, _ = _operator(client, cleanup)
    h_b, _org_b, _ = _operator(client, cleanup)
    theirs = _add_teacher(client, cleanup, h_b, "Not Yours", "+919800000110")

    r = client.post(f"/api/v1/platform/orgs/{org_a}/setup/logins", headers=h_a,
                    json={"logins": [{"user_id": theirs,
                                      "username": f"x.{uuid.uuid4().hex[:8]}"}]})
    assert r.status_code == 404, r.text


def test_the_operators_own_account_cannot_be_renamed_here(client, cleanup):
    h, org_id, operator_id = _operator(client, cleanup)
    r = client.post(f"/api/v1/platform/orgs/{org_id}/setup/logins", headers=h,
                    json={"logins": [{"user_id": operator_id,
                                      "username": f"vendor.{uuid.uuid4().hex[:8]}"}]})
    assert r.status_code == 404, r.text


def test_blank_password_leaves_the_existing_one_alone(client, cleanup):
    h, org_id, _ = _operator(client, cleanup)
    teacher_id = _add_teacher(client, cleanup, h, "Hema K", "+919800000111")
    db = AdminSession()
    try:
        before = db.get(User, uuid.UUID(teacher_id)).password_hash
    finally:
        db.close()

    r = client.post(f"/api/v1/platform/orgs/{org_id}/setup/logins", headers=h,
                    json={"logins": [{"user_id": teacher_id,
                                      "username": f"hema.{uuid.uuid4().hex[:8]}",
                                      "password": "   "}]})
    assert r.status_code == 200, r.text
    assert r.json()["passwords_set"] == 0

    db = AdminSession()
    try:
        assert db.get(User, uuid.UUID(teacher_id)).password_hash == before
    finally:
        db.close()


def test_a_short_password_is_refused(client, cleanup):
    h, org_id, _ = _operator(client, cleanup)
    teacher_id = _add_teacher(client, cleanup, h, "Iqbal R", "+919800000112")
    r = client.post(f"/api/v1/platform/orgs/{org_id}/setup/logins", headers=h,
                    json={"logins": [{"user_id": teacher_id,
                                      "username": f"iqbal.{uuid.uuid4().hex[:8]}",
                                      "password": "short"}]})
    assert r.status_code in (400, 422), r.text


def test_a_school_admin_cannot_reach_the_operator_routes(client, cleanup):
    """Negative authorization: these are the vendor's routes, not the school's."""
    reg = _register(client, cleanup)  # NOT promoted
    h = {"Authorization": f"Bearer {reg['access_token']}"}
    org_id = reg["org"]["id"]

    assert client.get(f"/api/v1/platform/orgs/{org_id}/setup/logins",
                      headers=h).status_code == 403
    assert client.get("/api/v1/platform/username-check", headers=h,
                      params={"username": "anything"}).status_code == 403
    assert client.post(f"/api/v1/platform/orgs/{org_id}/setup/logins", headers=h,
                       json={"logins": [{"user_id": reg["user"]["id"],
                                         "username": "whatever"}]}).status_code == 403


def test_saved_rows_come_back_for_a_reload(client, cleanup):
    """The list is re-read from the database, so a page refresh mid-edit does not
    lose the section — passwords are already unreadable by then, which is why no
    password comes back with it."""
    h, org_id, _ = _operator(client, cleanup)
    teacher_id = _add_teacher(client, cleanup, h, "Jaya L", "+919800000113")
    wanted = f"jaya.{uuid.uuid4().hex[:8]}"

    client.post(f"/api/v1/platform/orgs/{org_id}/setup/logins", headers=h,
                json={"logins": [{"user_id": teacher_id, "username": wanted}]})

    rows = client.get(f"/api/v1/platform/orgs/{org_id}/setup/logins", headers=h).json()
    row = next(r for r in rows if r["user_id"] == teacher_id)
    assert row["username"] == wanted
    assert row["org_role"] == "teacher"
    assert "password" not in row

    db = AdminSession()
    try:
        assert db.scalar(select(Membership.org_role).where(
            Membership.user_id == uuid.UUID(teacher_id))) == "teacher"
    finally:
        db.close()
