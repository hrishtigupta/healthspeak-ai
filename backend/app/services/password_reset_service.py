"""Forgot-password by one-time code sent to the patient's mobile number.

Safety rules:
- Patients only. Staff, doctor and admin accounts are still reset by an administrator.
- The request step always looks the same, so nobody can discover which numbers have accounts.
- Codes are 6 digits, valid for OTP_TTL_MINUTES, stored only as a hash, locked after
  OTP_MAX_ATTEMPTS wrong tries, and a new code cancels the old one.
- A successful reset signs the account out everywhere and clears any login lockout.
"""

import hashlib
import hmac
import logging
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.enums import Role
from app.core.security import burn_password_check, hash_password
from app.database.models import AuthSession, PasswordResetCode
from app.services import audit_service, sms_service, user_service

log = logging.getLogger("healthspeak.password_reset")


class InvalidCode(Exception):
    """Wrong, expired, used or locked code (deliberately not more specific)."""


def _now() -> datetime:
    return datetime.now(UTC)


def _hash(code_id, code: str) -> str:
    return hashlib.sha256(f"{code_id}:{code}".encode()).hexdigest()


def request_code(db: Session, identifier: str) -> None:
    """Send a code if the identifier belongs to an active patient with a mobile number."""
    s = get_settings()
    user = user_service.find_by_identifier(db, identifier)
    if user is None or user.role != Role.PATIENT.value or not user.is_active or not user.phone:
        audit_service.record(db, "password_reset.requested", details={"sent": False})
        db.commit()
        return
    now = _now()
    recent = list(db.scalars(select(PasswordResetCode.created_at).where(
        PasswordResetCode.user_id == user.id, PasswordResetCode.created_at > now - timedelta(hours=1))))
    if len(recent) >= s.otp_max_per_hour or any(
            c > now - timedelta(seconds=s.otp_resend_seconds) for c in recent):
        audit_service.record(db, "password_reset.throttled", actor_user_id=user.id)
        db.commit()
        return
    # A new code cancels any earlier unused one.
    db.execute(update(PasswordResetCode).where(
        PasswordResetCode.user_id == user.id, PasswordResetCode.used_at.is_(None)).values(used_at=now))
    code = f"{secrets.randbelow(10**6):06d}"
    row = PasswordResetCode(user_id=user.id, code_hash="", expires_at=now + timedelta(minutes=s.otp_ttl_minutes))
    db.add(row)
    db.flush()
    row.code_hash = _hash(row.id, code)
    try:
        sms_service.send_sms(
            user.phone,
            f"HealthSpeak AI: your password reset code is {code}. It expires in "
            f"{s.otp_ttl_minutes} minutes. Do not share it with anyone.")
        sent = True
    except sms_service.SmsNotSent as e:
        log.error("Password reset SMS not sent: %s", e)
        row.used_at = now  # nothing was delivered, so the code is worthless
        sent = False
    audit_service.record(db, "password_reset.requested", actor_user_id=user.id, details={"sent": sent})
    db.commit()


def confirm(db: Session, identifier: str, code: str, new_password: str) -> None:
    """Set a new password if the code is right. Raises InvalidCode otherwise."""
    s = get_settings()
    now = _now()
    user = user_service.find_by_identifier(db, identifier)
    row = None
    if user is not None and user.role == Role.PATIENT.value and user.is_active:
        row = db.scalar(select(PasswordResetCode).where(
            PasswordResetCode.user_id == user.id, PasswordResetCode.used_at.is_(None),
            PasswordResetCode.expires_at > now).order_by(PasswordResetCode.created_at.desc()).limit(1))
    if row is None:
        burn_password_check(code)
        raise InvalidCode
    if not hmac.compare_digest(row.code_hash, _hash(row.id, code.strip())):
        row.failed_attempts += 1
        if row.failed_attempts >= s.otp_max_attempts:
            row.used_at = now
        audit_service.record(db, "password_reset.failed", actor_user_id=user.id,
                             details={"locked": row.used_at is not None})
        db.commit()
        raise InvalidCode
    row.used_at = now
    user.password_hash = hash_password(new_password)
    user.failed_login_count = 0
    user.locked_until = None
    db.execute(update(AuthSession).where(
        AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None)).values(revoked_at=now))
    audit_service.record(db, "password_reset.completed", actor_user_id=user.id)
    db.commit()
