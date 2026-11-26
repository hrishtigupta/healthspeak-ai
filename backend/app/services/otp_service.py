"""One-time codes by SMS, shared by forgot-password and phone verification.

Rules: 6 digits, valid OTP_TTL_MINUTES, stored only as a hash, locked after OTP_MAX_ATTEMPTS wrong
tries, a new code cancels the old one of the same purpose, resend/hourly limits per account.
"""

import hashlib
import hmac
import logging
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import burn_password_check
from app.database.models import PasswordResetCode, User
from app.services import audit_service, sms_service

log = logging.getLogger("healthspeak.otp")

PASSWORD_RESET = "password_reset"
PHONE_CHANGE = "phone_change"


class InvalidCode(Exception):
    """Wrong, expired, used or locked code (deliberately not more specific)."""


class Throttled(Exception):
    """Too many codes requested (resend gap or hourly limit)."""


class SendFailed(Exception):
    """The SMS provider did not accept the message."""


@dataclass
class Issued:
    code_for_dev_echo: str | None  # only ever set in development with the console provider


def _now() -> datetime:
    return datetime.now(UTC)


def _hash(code_id, code: str) -> str:
    return hashlib.sha256(f"{code_id}:{code}".encode()).hexdigest()


def issue(db: Session, user: User, *, purpose: str, destination: str,
          new_phone: str | None = None) -> Issued:
    """Create a code and SMS it to `destination`. Raises Throttled or SendFailed."""
    s = get_settings()
    now = _now()
    recent = list(db.scalars(select(PasswordResetCode.created_at).where(
        PasswordResetCode.user_id == user.id, PasswordResetCode.purpose == purpose,
        PasswordResetCode.created_at > now - timedelta(hours=1))))
    if len(recent) >= s.otp_max_per_hour or any(
            c > now - timedelta(seconds=s.otp_resend_seconds) for c in recent):
        audit_service.record(db, f"{purpose}.throttled", actor_user_id=user.id)
        db.commit()
        raise Throttled
    db.execute(update(PasswordResetCode).where(
        PasswordResetCode.user_id == user.id, PasswordResetCode.purpose == purpose,
        PasswordResetCode.used_at.is_(None)).values(used_at=now))
    code = f"{secrets.randbelow(10**6):06d}"
    row = PasswordResetCode(user_id=user.id, code_hash="", purpose=purpose, new_phone=new_phone,
                            expires_at=now + timedelta(minutes=s.otp_ttl_minutes))
    db.add(row)
    db.flush()
    row.code_hash = _hash(row.id, code)
    try:
        sms_service.send_sms(
            destination,
            f"HealthSpeak AI: your verification code is {code}. It expires in "
            f"{s.otp_ttl_minutes} minutes. Do not share it with anyone.")
    except sms_service.SmsNotSent as e:
        log.error("OTP SMS not sent (%s): %s", purpose, e)
        row.used_at = now  # nothing was delivered, so the code is worthless
        audit_service.record(db, f"{purpose}.sms_failed", actor_user_id=user.id)
        db.commit()
        raise SendFailed(str(e)) from None
    audit_service.record(db, f"{purpose}.code_sent", actor_user_id=user.id,
                         details={"dev_echo": sms_service.dev_echo_allowed()})
    db.commit()
    return Issued(code if sms_service.dev_echo_allowed() else None)


def verify(db: Session, user: User | None, *, purpose: str, code: str) -> PasswordResetCode:
    """Return the matching live code row (already marked used). Raises InvalidCode."""
    s = get_settings()
    now = _now()
    row = None
    if user is not None:
        row = db.scalar(select(PasswordResetCode).where(
            PasswordResetCode.user_id == user.id, PasswordResetCode.purpose == purpose,
            PasswordResetCode.used_at.is_(None), PasswordResetCode.expires_at > now,
        ).order_by(PasswordResetCode.created_at.desc()).limit(1))
    if row is None:
        burn_password_check(code)
        raise InvalidCode
    if not hmac.compare_digest(row.code_hash, _hash(row.id, code.strip())):
        row.failed_attempts += 1
        if row.failed_attempts >= s.otp_max_attempts:
            row.used_at = now
        audit_service.record(db, f"{purpose}.failed", actor_user_id=user.id,
                             details={"locked": row.used_at is not None})
        db.commit()
        raise InvalidCode
    row.used_at = now
    return row
