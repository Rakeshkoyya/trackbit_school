"""The observance catalogue — platform data, curated by the operator (V1-7).

`D-60` chose *fetch and store in our database* over `S-123`'s checked file, and
the reason is scale: 28+ states × per year × multiple traditions is too much for
a hand-edited file, and a wrong date must be correctable without a deploy.
`S-149` answers the question that leaves open — **whose** database row is it —
with: nobody's. No `org_id`, no RLS, `require_super_admin` on every write, the
`demo_requests` shape from EN-1. One curation serves every school.

⚠️ **Storing a date in a database does not make it true.** Nothing in this file
sources a date; it stores what a human put in, alongside the `source` string
that says where they got it (`S-150`), and refuses to accept a row without one.
`Q-63` — what the real feeds are, and what the annual cycle is — is a research
task the founder schedules, and until it is answered the honest state of this
table is **empty**. An empty catalogue is a feed with no suggestions in it,
which is correct; a catalogue filled by asking a model when Diwali is would be
`S-123`'s rejected row wearing a table for a hat.
"""

import re
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models import EventDecision, Observance
from app.schemas.events import (
    ObservanceBulkIn,
    ObservanceBulkOut,
    ObservanceIn,
    ObservanceOut,
)


def slugify(name: str) -> str:
    """"Guru Purnima" → "guru-purnima". The key is what dismissal survives on
    (`S-148`), so it must be stable across years — derived from the name, never
    from the date."""
    s = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return s or "observance"


class ObservanceService:
    def __init__(self, db: Session):
        self.db = db

    def _counts(self, ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
        """How many schools have already decided on each entry — one grouped
        query, so the operator knows whether editing a date is an edit or a
        correction to something schools have already acted on."""
        if not ids:
            return {}
        rows = self.db.execute(
            select(EventDecision.observance_id, func.count(EventDecision.id))
            .where(EventDecision.observance_id.in_(ids))
            .group_by(EventDecision.observance_id)).all()
        return {oid: int(n) for oid, n in rows if oid}

    def list(self, *, year: int | None = None, state: str | None = None,
             q: str | None = None, include_inactive: bool = True) -> list[ObservanceOut]:
        stmt = select(Observance)
        if year:
            stmt = stmt.where(func.extract("year", Observance.date) == year)
        if state:
            stmt = stmt.where(Observance.state == state)
        if q:
            stmt = stmt.where(Observance.name.ilike(f"%{q}%"))
        if not include_inactive:
            stmt = stmt.where(Observance.is_active.is_(True))
        rows = list(self.db.scalars(stmt.order_by(Observance.date, Observance.name)))
        counts = self._counts([r.id for r in rows])
        out = []
        for r in rows:
            item = ObservanceOut.model_validate(r)
            item.decided_count = counts.get(r.id, 0)
            out.append(item)
        return out

    def create(self, body: ObservanceIn, user_id: uuid.UUID | None) -> ObservanceOut:
        row = Observance(
            key=body.key or slugify(body.name), name=body.name, date=body.date,
            end_date=body.end_date, kind=body.kind, tier=body.tier,
            prep_days=body.prep_days, state=body.state, board=body.board,
            tradition=body.tradition, source=body.source, note=body.note,
            is_active=body.is_active, created_by_user_id=user_id)
        self.db.add(row)
        self.db.flush()
        return ObservanceOut.model_validate(row)

    def update(self, observance_id: uuid.UUID, body: ObservanceIn) -> ObservanceOut:
        """Corrections are the point of this table existing (`D-60`), so an
        entry IS editable — unlike the school's own decision log, which is
        append-only. The two are different kinds of record: this is reference
        data, that is history."""
        row = self.db.scalar(select(Observance).where(Observance.id == observance_id))
        if row is None:
            raise NotFoundError("Observance")
        row.key = body.key or row.key
        row.name = body.name
        row.date = body.date
        row.end_date = body.end_date
        row.kind = body.kind
        row.tier = body.tier
        row.prep_days = body.prep_days
        row.state = body.state
        row.board = body.board
        row.tradition = body.tradition
        row.source = body.source
        row.note = body.note
        row.is_active = body.is_active
        self.db.flush()
        out = ObservanceOut.model_validate(row)
        out.decided_count = self._counts([row.id]).get(row.id, 0)
        return out

    def retire(self, observance_id: uuid.UUID) -> None:
        """Never a delete: a school may already have approved against this row,
        and the decision log points at it."""
        row = self.db.scalar(select(Observance).where(Observance.id == observance_id))
        if row is None:
            raise NotFoundError("Observance")
        row.is_active = False
        self.db.flush()

    def bulk(self, body: ObservanceBulkIn, user_id: uuid.UUID | None) -> ObservanceBulkOut:
        """A year's import from one source, upserted on (key, date).

        `S-151` — the realistic architecture is a small importer per source plus
        one annual human review, not "an API we call": state school holidays are
        gazette PDFs published per state, religious dates come from almanacs
        that disagree regionally, and only the UN observance list is cleanly
        machine-readable. So this takes rows from whatever produced them and
        makes re-running a corrected file **fix** every school instead of
        double-suggesting to all of them.
        """
        out = ObservanceBulkOut()
        for e in body.entries:
            key = e.key or slugify(e.name)
            row = self.db.scalar(select(Observance).where(
                Observance.key == key, Observance.date == e.date))
            if row is None:
                row = Observance(key=key, date=e.date, source=e.source or body.source,
                                 name=e.name, created_by_user_id=user_id)
                self.db.add(row)
                out.created += 1
            else:
                out.updated += 1
            row.name = e.name
            row.end_date = e.end_date
            row.kind = e.kind
            row.tier = e.tier
            row.prep_days = e.prep_days
            row.state = e.state
            row.board = e.board
            row.tradition = e.tradition
            row.source = e.source or body.source
            row.note = e.note
            row.is_active = e.is_active
        self.db.flush()
        return out
