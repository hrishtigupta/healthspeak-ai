"""Add, verify or change a patient's own mobile number (always proven with an SMS code).

- The code goes to the NEW number. The current number keeps working (login and password reset)
  until the code is confirmed; an unconfirmed number never replaces it and is never "verified".
- A number can belong to only one login account (users.phone is unique): the request is refused
  if another account already uses it, and the check is repeated when the code is confirmed.
- Only the logged-in patient can change their own number (the router passes that user in).
"""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.models import Patient, User
from app.services import audit_service, otp_service

InvalidCode = otp_service.InvalidCode
SendFailed = otp_service.SendFailed
Throttled = otp_service.Throttled


class PhoneInUse(Exception):
    """Another account already uses this number."""


class AlreadyVerified(Exception):
    """This is already the account's verified number."""


def _in_use_by_other(db: Session, user: User, phone: str) -> bool:
    return db.scalar(select(User.id).where(User.phone == phone, User.id != user.id)) is not None


def request_code(db: Session, user: User, phone: str) -> otp_service.Issued:
    if user.phone == phone and user.phone_verified_at is not None:
        raise AlreadyVerified
    if _in_use_by_other(db, user, phone):
        audit_service.record(db, "phone_change.refused_in_use", actor_user_id=user.id)
        db.commit()
        raise PhoneInUse
    return otp_service.issue(db, user, purpose=otp_service.PHONE_CHANGE, destination=phone, new_phone=phone)


def confirm(db: Session, user: User, patient: Patient, code: str) -> Patient:
    """Replace the number with the one the code was sent to. Raises InvalidCode / PhoneInUse."""
    row = otp_service.verify(db, user, purpose=otp_service.PHONE_CHANGE, code=code)
    new_phone = row.new_phone
    if not new_phone:
        raise InvalidCode
    if _in_use_by_other(db, user, new_phone):  # someone else took it while the code was pending
        db.rollback()
        raise PhoneInUse
    old_present = user.phone is not None
    user.phone = new_phone
    user.phone_verified_at = datetime.now(UTC)
    patient.phone = new_phone
    audit_service.record(db, "phone_change.completed", actor_user_id=user.id,
                         target_type="patient", target_id=patient.id,
                         details={"had_previous_number": old_present})
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise PhoneInUse from None
    db.refresh(patient)
    return patient
