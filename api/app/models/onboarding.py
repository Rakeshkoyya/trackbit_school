"""⚠️ RETIRED — the ten-step setup wizard it tracked is gone.

Setup is now one uploaded workbook on the operator's screen
(`SETUP-REDESIGN-PLAN`, `services/setup_pack/`), which needs no resume state:
the pack IS the state, and re-uploading a corrected one is the resume.
`services/wizard.py`, its endpoints and its schemas were deleted; nothing reads
this model any more.

**The table is still here on purpose.** Prod migrates *before* code deploys, so
dropping `onboarding_state` in the same change would leave the still-running old
build reading a table that no longer exists. Drop it in a follow-up migration
once this release is out — the ordinary two-step for a destructive schema change,
not an oversight.

Original intent, for anyone reading the table: one resumable row per org; the
wizard wrote through to the real tables at each confirmed step and kept only
per-step answers here, so progress was always derived from real data.
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
