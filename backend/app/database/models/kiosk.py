"""D8 Kiosk and Voice AI Status: registered kiosks and their heartbeats."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.models.mixins import Timestamps, UuidPk


class Kiosk(UuidPk, Timestamps, Base):
    """A shared patient-facing device. It authenticates its heartbeat with a
    secret key; only the key's SHA-256 hash is stored."""

    __tablename__ = "kiosks"

    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    location: Mapped[str | None] = mapped_column(String(200))
    key_hash: Mapped[str] = mapped_column(String(64), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    app_version: Mapped[str | None] = mapped_column(String(40))
    # Last self-reported device state, e.g. {"microphone": "granted", "ui_language": "hi"}.
    last_report: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"))
