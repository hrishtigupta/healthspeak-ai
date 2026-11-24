"""In-app notifications. Messages are short and contain no clinical details."""

import uuid

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.clock import now_utc
from app.database.models import Notification, User


def notify(db: Session, user_id: uuid.UUID | None, kind: str, title: str, body: str) -> None:
    """Queue a notification in the current transaction (the caller commits)."""
    if user_id is None:
        return
    db.add(Notification(user_id=user_id, kind=kind, title=title[:120], body=body[:500]))


def list_for(db: Session, user: User, *, unread_only: bool = False, limit: int = 50) -> list[Notification]:
    q = select(Notification).where(Notification.user_id == user.id)
    if unread_only:
        q = q.where(Notification.read_at.is_(None))
    return list(db.scalars(q.order_by(Notification.created_at.desc()).limit(limit)))


def unread_count(db: Session, user: User) -> int:
    return db.scalar(select(func.count()).select_from(Notification).where(
        Notification.user_id == user.id, Notification.read_at.is_(None))) or 0


def mark_read(db: Session, user: User, notification_id: uuid.UUID) -> bool:
    n = db.get(Notification, notification_id)
    if n is None or n.user_id != user.id:
        return False
    if n.read_at is None:
        n.read_at = now_utc()
        db.commit()
    return True


def mark_all_read(db: Session, user: User) -> None:
    db.execute(update(Notification).where(Notification.user_id == user.id, Notification.read_at.is_(None))
               .values(read_at=now_utc()))
    db.commit()
