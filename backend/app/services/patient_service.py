"""Patient registration, profile updates and consent history."""

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.consent import CONSENT_VERSION
from app.core.enums import ConsentMethod, ConsentType, Role
from app.core.security import normalize_phone
from app.database.models import ConsentRecord, Patient, User
from app.schemas.patient import (
    ConsentDecision,
    ConsentStatus,
    PatientCreateByStaff,
    PatientOut,
    PatientSelfRegister,
    PatientUpdate,
)
from app.services import audit_service, user_service


class ConsentVersionMismatch(Exception):
    """The patient was shown wording other than the current version."""


class ConsentRequired(Exception):
    """Registration needs consent to be granted."""


def _age(dob: date) -> int:
    today = datetime.now(UTC).date()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def latest_consent(patient: Patient, consent_type: ConsentType = ConsentType.DATA_PROCESSING):
    records = [c for c in patient.consents if c.consent_type == consent_type.value]
    return max(records, key=lambda c: c.created_at) if records else None


def consent_status(patient: Patient) -> ConsentStatus:
    rec = latest_consent(patient)
    if rec is None:
        return ConsentStatus(granted=False, version=None, is_current_version=False, recorded_at=None)
    return ConsentStatus(
        granted=rec.granted, version=rec.version,
        is_current_version=rec.version == CONSENT_VERSION, recorded_at=rec.created_at,
    )


def has_valid_consent(patient: Patient) -> bool:
    s = consent_status(patient)
    return s.granted and s.is_current_version


def to_out(patient: Patient) -> PatientOut:
    return PatientOut(
        id=patient.id, full_name=patient.full_name, date_of_birth=patient.date_of_birth,
        age=_age(patient.date_of_birth), gender=patient.gender, phone=patient.phone,
        email=patient.email, preferred_language=patient.preferred_language,
        has_account=patient.user_id is not None, consent=consent_status(patient),
        created_at=patient.created_at,
    )


def _check_consent(decision: ConsentDecision, *, must_grant: bool) -> None:
    if decision.version != CONSENT_VERSION:
        raise ConsentVersionMismatch
    if must_grant and not decision.granted:
        raise ConsentRequired


def _add_consent(db: Session, patient: Patient, decision: ConsentDecision,
                 method: ConsentMethod, recorded_by: uuid.UUID | None) -> ConsentRecord:
    rec = ConsentRecord(
        patient=patient, consent_type=ConsentType.DATA_PROCESSING.value, version=decision.version,
        granted=decision.granted, method=method.value, language=decision.language.value,
        recorded_by_user_id=recorded_by,
    )
    db.add(rec)
    db.flush()
    audit_service.record(
        db, "consent.granted" if decision.granted else "consent.withdrawn",
        actor_user_id=recorded_by, target_type="patient", target_id=patient.id,
        details={"version": decision.version, "method": method.value},
    )
    return rec


def register_self(db: Session, data: PatientSelfRegister) -> tuple[User, Patient]:
    """Create the patient's login account, profile and first consent in ONE transaction."""
    _check_consent(data.consent, must_grant=True)
    user = user_service.create_user(
        db, full_name=data.full_name, password=data.password, role=Role.PATIENT,
        email=data.email, phone=data.phone, ui_language=data.ui_language, commit=False,
    )
    patient = Patient(
        user_id=user.id, full_name=data.full_name, date_of_birth=data.date_of_birth,
        gender=data.gender.value, phone=data.phone, email=data.email,
        preferred_language=data.preferred_language.value, registered_by_user_id=user.id,
    )
    db.add(patient)
    db.flush()
    _add_consent(db, patient, data.consent, ConsentMethod.SELF_SERVICE, user.id)
    audit_service.record(db, "patient.registered", actor_user_id=user.id,
                         target_type="patient", target_id=patient.id, details={"method": "self_service"})
    db.commit()
    db.refresh(patient)
    return user, patient


def register_by_staff(db: Session, data: PatientCreateByStaff, staff: User) -> Patient:
    _check_consent(data.consent, must_grant=True)
    patient = Patient(
        full_name=data.full_name, date_of_birth=data.date_of_birth, gender=data.gender.value,
        phone=data.phone, email=data.email, preferred_language=data.preferred_language.value,
        registered_by_user_id=staff.id,
    )
    db.add(patient)
    db.flush()
    _add_consent(db, patient, data.consent, ConsentMethod.STAFF_ASSISTED, staff.id)
    audit_service.record(db, "patient.registered", actor_user_id=staff.id,
                         target_type="patient", target_id=patient.id, details={"method": "staff"})
    db.commit()
    db.refresh(patient)
    return patient


def record_consent(db: Session, patient: Patient, decision: ConsentDecision, actor: User) -> ConsentRecord:
    _check_consent(decision, must_grant=False)
    method = ConsentMethod.SELF_SERVICE if actor.id == patient.user_id else ConsentMethod.STAFF_ASSISTED
    rec = _add_consent(db, patient, decision, method, actor.id)
    db.commit()
    db.refresh(patient)
    return rec


def get_for_user(db: Session, user: User) -> Patient | None:
    return db.scalar(select(Patient).where(Patient.user_id == user.id))


def get(db: Session, patient_id: uuid.UUID) -> Patient | None:
    return db.get(Patient, patient_id)


def update(db: Session, patient: Patient, data: PatientUpdate, actor: User) -> Patient:
    changes = data.model_dump(exclude_unset=True, exclude_none=True)
    changed = []
    for field, value in changes.items():
        value = getattr(value, "value", value)
        if getattr(patient, field) != value:
            setattr(patient, field, value)
            changed.append(field)
    if "full_name" in changed and patient.user_id is not None:
        # Keep the login account's display name in step with the profile.
        account = db.get(User, patient.user_id)
        if account is not None:
            account.full_name = patient.full_name
    if changed:
        # Record WHICH fields changed, never their values (they are personal data).
        audit_service.record(db, "patient.updated", actor_user_id=actor.id, target_type="patient",
                             target_id=patient.id, details={"fields": sorted(changed)})
        db.commit()
        db.refresh(patient)
    return patient


def search(db: Session, q: str | None, *, limit: int, offset: int) -> tuple[list[Patient], int]:
    stmt = select(Patient)
    if q and q.strip():
        q = q.strip()
        conds = [Patient.full_name.ilike(f"%{_escape_like(q)}%", escape="\\")]
        phone = normalize_phone(q, get_settings().default_phone_country_code)
        if phone:
            conds.append(Patient.phone == phone)
        digits = "".join(ch for ch in q if ch.isdigit())
        if len(digits) >= 4:
            conds.append(Patient.phone.like(f"%{digits}"))
        stmt = stmt.where(or_(*conds))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = list(db.scalars(stmt.order_by(Patient.created_at.desc(), Patient.id).limit(limit).offset(offset)))
    return rows, total


def _escape_like(s: str) -> str:
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def audit_view(db: Session, patient: Patient, actor: User) -> None:
    """Record that a staff member opened a patient record."""
    audit_service.record(db, "patient.viewed", actor_user_id=actor.id,
                         target_type="patient", target_id=patient.id)
    db.commit()
