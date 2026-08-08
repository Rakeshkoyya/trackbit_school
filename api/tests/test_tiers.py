"""`services/tiers.py` — pricing, assignment and the upgrade queue (P3).

No endpoints exist yet (they land in P4/P7), so these drive the service
directly. The two that matter most are
`test_a_price_rise_does_not_reprice_an_existing_school` and
`test_only_an_admin_may_raise_a_request` — one protects every school's invoice,
the other protects the operator's inbox.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, text

from app.core.context import CurrentMember
from app.core.exceptions import ForbiddenError, ValidationError
from app.models import Membership, Organization, PlanChange, Student, User
from app.schemas.tiers import (
    AssignPlanIn,
    SetPriceIn,
    UpgradeRequestIn,
    UpgradeRequestNoteIn,
)
from app.services.tiers import TierService
from tests.conftest import AdminSession

STUDENTS = 3


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def ctx(client, unique_email, cleanup):
    """A school with a known student count, an admin, and a teacher."""
    reg = client.post(
        "/api/v1/auth/register-org",
        json={"org_name": "Tier Co", "name": "Adam Admin", "email": unique_email,
              "password": "supersecret1", "timezone": "Asia/Kolkata"},
    ).json()
    org_id = uuid.UUID(reg["org"]["id"])
    cleanup["orgs"].append(org_id)
    cleanup["users"].append(uuid.UUID(reg["user"]["id"]))

    inv = client.post(
        "/api/v1/org/members/invite", headers=_auth(reg["access_token"]),
        json={"name": "Tina Teacher", "phone": "+919812345670", "role": "teacher"},
    ).json()
    cleanup["users"].append(uuid.UUID(inv["user_id"]))

    db = AdminSession()
    try:
        for i in range(STUDENTS):
            db.add(Student(org_id=org_id, full_name=f"Kid {i}",
                           admission_no=f"ADM-{uuid.uuid4().hex[:8]}"))
        db.commit()
    finally:
        db.close()

    return {"org_id": org_id, "admin_user_id": uuid.UUID(reg["user"]["id"]),
            "teacher_user_id": uuid.UUID(inv["user_id"])}


@pytest.fixture
def db(ctx):
    """A privileged session already scoped to the org, so writes to the
    RLS-protected tier tables satisfy their WITH CHECK."""
    session = AdminSession()
    session.execute(text("SELECT set_config('app.current_org_id', :v, false)"),
                    {"v": str(ctx["org_id"])})
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def _member(db, org_id, user_id) -> CurrentMember:
    return CurrentMember(
        user=db.get(User, user_id),
        org=db.get(Organization, org_id),
        membership=db.scalar(select(Membership).where(
            Membership.org_id == org_id, Membership.user_id == user_id)),
    )


# ---- pricing + assignment ---------------------------------------------
def test_seeded_launch_prices(db):
    prices = {p.plan: p.amount_paise_per_student for p in TierService(db).list_prices()}
    # The founder's launch numbers, in paise: free ₹0 · pro ₹10 · max ₹25 · ultra ₹80.
    assert prices == {"free": 0, "pro": 1000, "max": 2500, "ultra": 8000}


def test_assign_plan_appends_history_and_caches_on_the_org(db, ctx):
    svc = TierService(db)
    out = svc.assign_plan(ctx["admin_user_id"], ctx["org_id"],
                          AssignPlanIn(plan="max", reason="paid by cheque"))

    assert out.from_plan == "free" and out.to_plan == "max"
    assert out.student_count_at_change == STUDENTS
    assert out.unit_amount_snapshot == 2500
    assert out.monthly_amount_snapshot == 2500 * STUDENTS

    org = db.get(Organization, ctx["org_id"])
    assert org.plan == "max"
    # `D-106`: this is what makes the Razorpay webhook keep its hands off.
    assert org.plan_source == "manual"
    assert org.plan_status == "active"

    rows = db.scalars(select(PlanChange).where(
        PlanChange.org_id == ctx["org_id"])).all()
    assert len(rows) == 1


def test_a_downgrade_is_another_append_never_an_edit(db, ctx):
    """Law 3: undo is a compensating row. The history keeps both moves."""
    svc = TierService(db)
    svc.assign_plan(ctx["admin_user_id"], ctx["org_id"], AssignPlanIn(plan="ultra"))
    svc.assign_plan(ctx["admin_user_id"], ctx["org_id"], AssignPlanIn(plan="free"))

    history = svc.history(ctx["org_id"])
    assert [h.to_plan for h in history] == ["free", "ultra"]  # newest first
    assert history[0].from_plan == "ultra"
    assert db.get(Organization, ctx["org_id"]).plan_status == "none"


def test_a_price_rise_does_not_reprice_an_existing_school(db, ctx):
    """`D-106` — the whole reason amounts are snapshotted.

    Prices "might change regularly because we are just launching". A school
    sold at ₹10 keeps paying ₹10 when the list moves to ₹15; only the quote a
    NEW school sees changes.
    """
    svc = TierService(db)
    svc.assign_plan(ctx["admin_user_id"], ctx["org_id"], AssignPlanIn(plan="pro"))
    svc.set_price(ctx["admin_user_id"],
                  SetPriceIn(plan="pro", amount_paise_per_student=1500,
                             note="launch promo ended"))

    signed = svc.history(ctx["org_id"])[0]
    assert signed.unit_amount_snapshot == 1000, "the school's own rate must not move"
    assert signed.monthly_amount_snapshot == 1000 * STUDENTS

    quoted = next(t for t in svc.quote(db.get(Organization, ctx["org_id"])).tiers
                  if t.plan == "pro")
    assert quoted.unit_paise_per_student == 1500, "the LIST price is what moved"


def test_quote_carries_this_schools_own_multiplier(db, ctx):
    q = TierService(db).quote(db.get(Organization, ctx["org_id"]))
    assert q.current_plan == "free" and q.students == STUDENTS
    ultra = next(t for t in q.tiers if t.plan == "ultra")
    # The wall shows its working: ₹80 × 3 students, never a bare total.
    assert ultra.unit_paise_per_student == 8000
    assert ultra.monthly_paise == 8000 * STUDENTS
    assert ultra.is_upgrade and not ultra.is_current
    assert "agent.mcp" in ultra.features
    assert next(t for t in q.tiers if t.plan == "free").is_current


def test_unknown_plan_is_refused(db, ctx):
    with pytest.raises(ValidationError) as exc:
        TierService(db).assign_plan(ctx["admin_user_id"], ctx["org_id"],
                                    AssignPlanIn(plan="platinum"))
    assert exc.value.code == "unknown_plan"


# ---- the upgrade request ----------------------------------------------
def test_only_an_admin_may_raise_a_request(db, ctx):
    """`D-110` — one locked screen must not generate forty requests from forty
    teachers for the operator to dedupe by hand."""
    teacher = _member(db, ctx["org_id"], ctx["teacher_user_id"])
    with pytest.raises(ForbiddenError) as exc:
        TierService(db).raise_request(teacher, UpgradeRequestIn(plan="pro"))
    assert exc.value.code == "admin_only"
    assert "contact your school admin" in exc.value.message.lower()


def test_raise_request_is_idempotent_while_one_is_open(db, ctx):
    svc = TierService(db)
    admin = _member(db, ctx["org_id"], ctx["admin_user_id"])
    first = svc.raise_request(admin, UpgradeRequestIn(
        plan="pro", feature_id="fees.collection"))
    again = svc.raise_request(admin, UpgradeRequestIn(plan="max"))
    assert again.id == first.id, "asking twice is the same ask, not a second row"
    assert again.requested_plan == "pro"


def test_a_request_must_actually_be_an_upgrade(db, ctx):
    svc = TierService(db)
    svc.assign_plan(ctx["admin_user_id"], ctx["org_id"], AssignPlanIn(plan="max"))
    admin = _member(db, ctx["org_id"], ctx["admin_user_id"])
    with pytest.raises(ValidationError) as exc:
        svc.raise_request(admin, UpgradeRequestIn(plan="pro"))
    assert exc.value.code == "not_an_upgrade"


def test_the_wall_records_which_feature_was_hit(db, ctx):
    """The product signal: which paywall converts, without anyone being asked."""
    svc = TierService(db)
    admin = _member(db, ctx["org_id"], ctx["admin_user_id"])
    svc.raise_request(admin, UpgradeRequestIn(
        plan="max", feature_id="tasks.boards", message="need the task board"))
    queued = [r for r in svc.list_requests() if r.org_id == ctx["org_id"]]
    assert len(queued) == 1
    row = queued[0]
    assert row.feature_id == "tasks.boards"
    assert row.org_name == "Tier Co" and row.current_plan == "free"
    assert row.students == STUDENTS
    assert row.monthly_paise == 2500 * STUDENTS  # quoted at the max list price


def test_notes_append_and_move_the_status_cache(db, ctx):
    svc = TierService(db)
    admin = _member(db, ctx["org_id"], ctx["admin_user_id"])
    req = svc.raise_request(admin, UpgradeRequestIn(plan="pro"))

    svc.add_note(ctx["admin_user_id"], req.id,
                 UpgradeRequestNoteIn(note="rang them, calling back Tuesday",
                                      status_to="contacted"))
    detail = svc.add_note(ctx["admin_user_id"], req.id,
                          UpgradeRequestNoteIn(note="paid by NEFT", status_to="won"))

    assert detail.request.status == "won"
    assert [n.status_to for n in detail.notes] == ["contacted", "won"]
    assert detail.notes[1].status_from == "contacted"
    # An answered request frees the school to ask again later.
    assert svc.open_request(ctx["org_id"]) is None


def test_an_empty_note_is_refused(db, ctx):
    svc = TierService(db)
    admin = _member(db, ctx["org_id"], ctx["admin_user_id"])
    req = svc.raise_request(admin, UpgradeRequestIn(plan="pro"))
    with pytest.raises(ValidationError) as exc:
        svc.add_note(ctx["admin_user_id"], req.id, UpgradeRequestNoteIn(note="   "))
    assert exc.value.code == "empty_note"


# ---- the expiry watch --------------------------------------------------
def test_expiring_soon_lists_only_dated_paid_plans(db, ctx):
    svc = TierService(db)
    soon = datetime.now(UTC) + timedelta(days=5)
    svc.assign_plan(ctx["admin_user_id"], ctx["org_id"],
                    AssignPlanIn(plan="pro", expires_at=soon))
    assert ctx["org_id"] in {o.id for o in svc.expiring_soon(days=30)}
    assert ctx["org_id"] not in {o.id for o in svc.expiring_soon(days=1)}

    # Nothing downgrades on its own — the plan is still pro after the date is
    # set. The operator reads the list and decides.
    assert db.get(Organization, ctx["org_id"]).plan == "pro"
