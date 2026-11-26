"""One-time codes for password reset. Only a hash of each code is stored."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.models.mixins import UuidPk


class PasswordResetCode(UuidPk, Base):
    __tablename__ = "password_reset_codes"
    __table_args__ = (Index("ix_password_reset_codes_user_created", "user_id", "created_at"),)

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"))
    code_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # "password_reset" | "phone_change". phone_change codes go to `new_phone`, which replaces the
    # account's number only after the code is confirmed.
    purpose: Mapped[str] = mapped_column(String(16), default="password_reset", server_default="password_reset")
    new_phone: Mapped[str | None] = mapped_column(String(16))
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    # Set when the code is used, replaced by a newer one, or locked after too many wrong tries.
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
