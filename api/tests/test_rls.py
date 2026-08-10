"""RLS safety-net test (P0-BE-02 done-when): cross-org reads are denied.

When `app.current_org_id` is set on the connection, org-scoped tables must only
expose rows for that org — even though app-layer query scoping is the primary
guard. Requires the migrated dev database to be reachable.
"""

import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import OperationalError

from app.core.database import SessionLocal
from app.models import Board, FeeEvent, Organization, TaskInstance, User
from tests.conftest import AdminSession


def _make_org(db, label: str) -> tuple[Organization, TaskInstance]:
    org = Organization(name=f"rls-{label}-{uuid.uuid4()}")
    db.add(org)
    db.flush()
    owner = User(name="owner", email=f"owner-{uuid.uuid4().hex[:8]}@example.com")
    db.add(owner)
    db.flush()
    board = Board(org_id=org.id, name="B", created_by=owner.id, owner_id=owner.id)
    db.add(board)
    db.flush()
    inst = TaskInstance(org_id=org.id, board_id=board.id, title="t", created_by=owner.id)
    db.add(inst)
    db.flush()
    return org, inst


def test_rls_denies_cross_org_reads():
    db = SessionLocal()
    try:
        try:
            org_a, task_a = _make_org(db, "A")
            _, task_b = _make_org(db, "B")
            db.flush()
        except OperationalError as exc:  # pragma: no cover
            pytest.skip(f"dev database not reachable: {exc}")

        # Scope this transaction to org A (transaction-local GUC).
        db.execute(
            text("SELECT set_config('app.current_org_id', :oid, true)"),
            {"oid": str(org_a.id)},
        )

        visible = set(db.execute(select(TaskInstance.id)).scalars().all())
        assert task_a.id in visible, "own-org rows must remain visible"
        assert task_b.id not in visible, "RLS must hide other orgs' rows"
    finally:
        db.rollback()  # never persist test fixtures
        db.close()


def test_tier_tables_carry_org_isolation():
    """Law 2: an org-scoped table gets its policy in its own migration.

    `plan_changes` and `upgrade_requests` are org-scoped and must be isolated.
    `plan_prices` and `upgrade_request_notes` deliberately are NOT — they are
    platform tables with no `org_id`, and the notes especially must stay
    unreachable from any org-scoped query (they hold the operator's commentary
    on a live negotiation about that very school).
    """
    db = AdminSession()
    try:
        policed = set(db.execute(text(
            "SELECT tablename FROM pg_policies WHERE tablename IN "
            "('plan_changes', 'upgrade_requests', 'plan_prices', "
            "'upgrade_request_notes')"
        )).scalars().all())
    finally:
        db.close()
    assert policed == {"plan_changes", "upgrade_requests"}


def test_fee_desk_tables_carry_org_isolation():
    """FE-1 (`b7c8d9e0f1a2`): the three new fee-desk tables are org-scoped.

    Worth asserting rather than assuming, because this suite's other tests are
    hardcoded per module — a new table gets no coverage at all unless somebody
    adds a line here, so "test_rls.py is green" would otherwise have said
    nothing whatsoever about these three.

    `fee_payment_proofs` holds photographs of families' cheques and `fee_events`
    holds a school's entire collection history with the name of every clerk who
    touched it. Neither is a table to leave to app-layer scoping alone.
    """
    db = AdminSession()
    try:
        policed = set(db.execute(text(
            "SELECT tablename FROM pg_policies WHERE policyname = 'org_isolation' "
            "AND tablename IN ('fee_payment_proofs', 'fee_events', "
            "'fee_receipt_counters')"
        )).scalars().all())
        # ENABLE alone is not enough: without FORCE the policy does not apply to
        # the table owner, which is the role migrations and the seed run as.
        unforced = set(db.execute(text(
            "SELECT c.relname FROM pg_class c WHERE c.relname IN "
            "('fee_payment_proofs', 'fee_events', 'fee_receipt_counters') "
            "AND NOT (c.relrowsecurity AND c.relforcerowsecurity)"
        )).scalars().all())
    finally:
        db.close()
    assert policed == {"fee_payment_proofs", "fee_events", "fee_receipt_counters"}
    assert unforced == set(), f"RLS not enabled+forced on: {sorted(unforced)}"


def test_rls_hides_another_orgs_fee_events():
    """The behavioural half of the test above, on the row that matters most.

    A policy row in `pg_policies` proves the migration ran; it does not prove the
    predicate is right. This writes one event per org and checks that a
    connection scoped to org A cannot see org B's — the actual promise.
    """
    db = SessionLocal()
    try:
        try:
            org_a, _ = _make_org(db, "fee-A")
            org_b, _ = _make_org(db, "fee-B")
            ev_a = FeeEvent(org_id=org_a.id, kind="note_added",
                            summary="A's event", actor_name="A clerk")
            ev_b = FeeEvent(org_id=org_b.id, kind="note_added",
                            summary="B's event", actor_name="B clerk")
            db.add_all([ev_a, ev_b])
            db.flush()
        except OperationalError as exc:  # pragma: no cover
            pytest.skip(f"dev database not reachable: {exc}")

        db.execute(
            text("SELECT set_config('app.current_org_id', :oid, true)"),
            {"oid": str(org_a.id)},
        )
        visible = set(db.execute(select(FeeEvent.id)).scalars().all())
        assert ev_a.id in visible, "own-org fee events must remain visible"
        assert ev_b.id not in visible, "RLS must hide another school's fee log"
    finally:
        db.rollback()
        db.close()
