"""Forgot-password by one-time code sent to the patient's mobile number.

Safety rules:
- Patients only. Staff, doctor and admin accounts are still reset by an administrator.
- If SMS cannot be delivered at all (not configured / provider refuses) the caller is TOLD, so
  nobody waits for a code that will never come. A system-wide "not configured" answer reveals
  nothing about any account; a provider refusal for one number is reported too (documented
  trade-off), but limited by the resend and hourly limits.
- For a number without a patient account nothing is sent and the answer looks like success.
- A successful reset signs the account out everywhere and clears any login lockout.
"""

from datetime import UTC, datetime

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.enums import Role
from app.core.security import hash_password
from app.database.models import AuthSession
from app.services import audit_service, otp_service, user_service

InvalidCode = otp_service.InvalidCode
SendFailed = otp_service.SendFailed


def request_code(db: Session, identifier: str) -> otp_service.Issued | None:
    """Send a code if the identifier belongs to an active patient with a mobile number.

    Returns Issued when a code was sent, None when nothing was sent for a benign reason
    (unknown / ineligible account, or the resend limit). Raises SendFailed on delivery failure.
    """
    user = user_service.find_by_identifier(db, identifier)
    if user is None or user.role != Role.PATIENT.value or not user.is_active or not user.phone:
        audit_service.record(db, "password_reset.requested", details={"sent": False})
        db.commit()
        return None
    try:
        return otp_service.issue(db, user, purpose=otp_service.PASSWORD_RESET, destination=user.phone)
    except otp_service.Throttled:
        return None


def confirm(db: Session, identifier: str, code: str, new_password: str) -> None:
    """Set a new password if the code is right. Raises InvalidCode otherwise."""
    user = user_service.find_by_identifier(db, identifier)
    if user is not None and not (user.role == Role.PATIENT.value and user.is_active):
        user = None
    row = otp_service.verify(db, user, purpose=otp_service.PASSWORD_RESET, code=code)
    now = datetime.now(UTC)
    user.password_hash = hash_password(new_password)
    user.failed_login_count = 0
    user.locked_until = None
    db.execute(update(AuthSession).where(
        AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None)).values(revoked_at=now))
    audit_service.record(db, "password_reset.completed", actor_user_id=user.id,
                         details={"code_id": str(row.id)})
    db.commit()
