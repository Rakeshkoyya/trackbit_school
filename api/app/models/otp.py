"""Phone OTP codes for parent login (parent portal).

Pre-identity: keyed by phone (the parent may not have a User row yet), so this
lives outside the user-bound auth_tokens table. Only the code's hash is stored;
an attempt counter caps brute force and expiry is minutes. Platform-level like
demo_requests: no org_id (one phone may span orgs) and no RLS policy.
"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import CreatedAtMixin, UUIDPKMixin


class OtpCode(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "otp_codes"

    # Normalized last-10-digit key — matching ignores +91 / spacing differences.
    phone_key: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    code_hash: Mapped[str] = mapped_column(Text, nullable=False)
    purpose: Mapped[str] = mapped_column(Text, nullable=False, server_default="parent_login")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    # Set on successful verify OR when superseded by a newer code request.
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
