"""Login, lockout, session creation/validation and logout."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import (
    burn_password_check,
    hash_password,
    hash_token,
    new_session_token,
    password_needs_rehash,
    verify_password,
)
from app.database.models import AuthSession, User
from app.services import audit_service, user_service


def _now() -> datetime:
    return datetime.now(UTC)


def authenticate(db: Session, identifier: str, password: str) -> User | None:
    """Return the user if the credentials are valid, else None.

    Every failure looks identical to the caller. Failed attempts count towards a
    temporary lockout. Commits the attempt's bookkeeping and audit event.
    """
    settings = get_settings()
    now = _now()
    user = user_service.find_by_identifier(db, identifier)

    if user is None:
        burn_password_check(password)
        audit_service.record(db, "login.failed", details={"reason": "unknown_account"})
        db.commit()
        return None

    if user.locked_until and user.locked_until > now:
        burn_password_check(password)
        audit_service.record(db, "login.failed", actor_user_id=user.id, details={"reason": "locked"})
        db.commit()
        return None

    if not verify_password(user.password_hash, password):
        user.failed_login_count += 1
        details = {"reason": "bad_password"}
        if user.failed_login_count >= settings.login_max_failed_attempts:
            user.locked_until = now + timedelta(minutes=settings.login_lockout_minutes)
            user.failed_login_count = 0
            details["locked"] = True
        audit_service.record(db, "login.failed", actor_user_id=user.id, details=details)
        db.commit()
        return None

    if not user.is_active:
        audit_service.record(db, "login.failed", actor_user_id=user.id, details={"reason": "inactive"})
        db.commit()
        return None

    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now
    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    return user


def start_session(db: Session, user: User) -> tuple[str, AuthSession]:
    """Create a session for an authenticated user. Returns (plain token, session row)."""
    token = new_session_token()
    session = AuthSession(
        user_id=user.id,
        token_hash=hash_token(token),
        expires_at=_now() + timedelta(minutes=get_settings().session_ttl_minutes),
    )
    db.add(session)
    audit_service.record(db, "login.success", actor_user_id=user.id)
    db.commit()
    db.refresh(session)
    return token, session


def resolve_session(db: Session, token: str) -> AuthSession | None:
    """The live session for a token, or None if unknown/expired/revoked/user inactive."""
    session = db.scalar(select(AuthSession).where(AuthSession.token_hash == hash_token(token)))
    if session is None or session.revoked_at is not None or session.expires_at <= _now():
        return None
    if not session.user.is_active:
        return None
    return session


def end_session(db: Session, session: AuthSession) -> None:
    session.revoked_at = _now()
    audit_service.record(db, "logout", actor_user_id=session.user_id)
    db.commit()
