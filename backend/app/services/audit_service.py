"""Record audit events. Adds to the session; the caller's commit persists them."""

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.database.models import AuditEvent


def record(
    db: Session,
    action: str,
    *,
    actor_user_id: uuid.UUID | None = None,
    target_type: str | None = None,
    target_id: str | uuid.UUID | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    db.add(
        AuditEvent(
            actor_user_id=actor_user_id,
            action=action,
            target_type=target_type,
            target_id=str(target_id) if target_id is not None else None,
            details=details,
        )
    )
