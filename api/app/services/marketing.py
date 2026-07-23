"""Marketing service — capture demo requests from the public site.

The write path runs unauthenticated, so it does exactly one thing: normalise the
submitted strings and insert one row. No lookups, no side effects the caller can
observe, nothing that could be used to probe for existing schools.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DemoRequest
from app.schemas.marketing import DemoRequestCreate, DemoRequestOut


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

    def list_demo_requests(self, limit: int = 200) -> list[DemoRequestOut]:
        """Newest first — the operator works the top of the list."""
        rows = self.db.execute(
            select(DemoRequest).order_by(DemoRequest.created_at.desc()).limit(limit)
        ).scalars().all()
        return [DemoRequestOut.model_validate(r, from_attributes=True) for r in rows]
