"""Marketing service — capture demo requests from the public site, and the
operator's working surface over them.

The write path runs unauthenticated, so it does exactly one thing: normalise the
submitted strings and insert one row. No lookups, no side effects the caller can
observe, nothing that could be used to probe for existing schools.

The operator side (super-admin only) is append-only: every status move and every
remark inserts a `demo_request_notes` row, and `demo_requests.status` is just the
cache of the newest one. Nothing an operator writes is edited or deleted, so a
lead's history stays the whole truth (law 3).
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.exceptions import NotFoundError, ValidationError
from app.models import DemoRequest, DemoRequestNote, User
from app.models.marketing import DEMO_REQUEST_STATUSES
from app.schemas.marketing import (
    DemoRequestCreate,
    DemoRequestDetail,
    DemoRequestNoteOut,
    DemoRequestOut,
    DemoRequestUpdate,
)

LIST_LIMIT = 200


class MarketingService:
    def __init__(self, db: Session):
        self.db = db

    def create_demo_request(self, body: DemoRequestCreate) -> DemoRequest:
        row = DemoRequest(
            school_name=body.school_name.strip(),
            contact_name=body.contact_name.strip(),
            email=str(body.email).strip().lower(),
            phone=body.phone.strip(),
            city=(body.city or "").strip() or None,
            student_count=body.student_count,
            message=(body.message or "").strip() or None,
            source=(body.source or "landing").strip() or "landing",
            status="new",
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    # ── operator reads ───────────────────────────────────────────────────────
    def _out(self, row: DemoRequest, note_count: int = 0,
             last_activity_at=None) -> DemoRequestOut:
        return DemoRequestOut(
            id=row.id, school_name=row.school_name, contact_name=row.contact_name,
            email=row.email, phone=row.phone, city=row.city,
            student_count=row.student_count, message=row.message, source=row.source,
            status=row.status, created_at=row.created_at, note_count=note_count,
            last_activity_at=last_activity_at or row.created_at,
        )

    def list_demo_requests(self, limit: int = LIST_LIMIT) -> list[DemoRequestOut]:
        """Newest first — the operator works the top of the list.

        The whole list comes back unfiltered so the screen can count each status
        for its filter chips; at a few hundred leads that is one query, and
        filtering server-side would make those counts lie.
        """
        rows = self.db.execute(
            select(DemoRequest).order_by(DemoRequest.created_at.desc()).limit(limit)
        ).scalars().all()
        if not rows:
            return []
        # One grouped query for the activity summary — never a query per lead.
        activity = {
            rid: (int(n), last) for rid, n, last in self.db.execute(
                select(DemoRequestNote.demo_request_id,
                       func.count(DemoRequestNote.id),
                       func.max(DemoRequestNote.created_at))
                .where(DemoRequestNote.demo_request_id.in_([r.id for r in rows]))
                .group_by(DemoRequestNote.demo_request_id)).all()
        }
        return [self._out(r, *activity.get(r.id, (0, None))) for r in rows]

    def _require(self, request_id: uuid.UUID) -> DemoRequest:
        row = self.db.get(DemoRequest, request_id)
        if row is None:
            raise NotFoundError("Demo request")
        return row

    def _notes(self, request_id: uuid.UUID) -> list[DemoRequestNoteOut]:
        rows = self.db.execute(
            select(DemoRequestNote, User.name)
            .outerjoin(User, User.id == DemoRequestNote.author_user_id)
            .where(DemoRequestNote.demo_request_id == request_id)
            .order_by(DemoRequestNote.created_at.desc())).all()
        return [
            DemoRequestNoteOut(
                id=n.id, created_at=n.created_at, author_name=author,
                note=n.note, status_from=n.status_from, status_to=n.status_to)
            for n, author in rows
        ]

    def demo_request_detail(self, request_id: uuid.UUID) -> DemoRequestDetail:
        row = self._require(request_id)
        notes = self._notes(request_id)
        base = self._out(row, len(notes), notes[0].created_at if notes else None)
        return DemoRequestDetail(**base.model_dump(), notes=notes)

    # ── operator writes (append-only) ────────────────────────────────────────
    def add_note(self, m: CurrentMember, request_id: uuid.UUID,
                 body: DemoRequestUpdate) -> DemoRequestDetail:
        """Record one operator action as one history row.

        Re-selecting the status the lead already has is not a move: the remark is
        stored and `status_from`/`status_to` stay null, so the history never
        fills with no-op transitions.
        """
        row = self._require(request_id)
        note = (body.note or "").strip() or None
        if body.status is not None and body.status not in DEMO_REQUEST_STATUSES:
            raise ValidationError(f"Unknown status '{body.status}'.")
        moved = body.status is not None and body.status != row.status
        if note is None and not moved:
            raise ValidationError("Nothing to record — write a remark or change the status.")

        entry = DemoRequestNote(
            demo_request_id=row.id,
            author_user_id=m.user.id,
            note=note,
            status_from=row.status if moved else None,
            status_to=body.status if moved else None,
        )
        self.db.add(entry)
        if moved:
            row.status = body.status   # derived cache of the newest status_to
        self.db.commit()
        return self.demo_request_detail(row.id)
