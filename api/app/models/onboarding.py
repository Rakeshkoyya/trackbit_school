"""Setup wizard state (V2-M1, SPRD2 §4.4, §5.1).

One resumable row per org. The wizard WRITES THROUGH to the real tables at each
confirmed step (no parallel store) — `payload` holds only per-step answers /
extractions kept for resume convenience (e.g. the year_id it created). Progress is
otherwise derived from the real data, so the wizard is always truthful after a
logout or a manual edit made outside it.
"""

import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import CreatedAtMixin, UUIDPKMixin


class OnboardingState(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "onboarding_state"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    current_step: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="in_progress")

    __table_args__ = (
        UniqueConstraint("org_id", name="uq_onboarding_state_org"),
        CheckConstraint("status IN ('in_progress', 'done')", name="status_valid"),
    )
