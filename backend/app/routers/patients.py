"""Patient self-registration, own profile, and staff patient management.

Access in this phase (least privilege):
- anyone:   GET /consent/current, POST /patients/register
- patient:  own profile and consent only (/patients/me...)
- staff:    register walk-ins, search, view, correct, record consent
- doctor/admin: no direct patient-record access yet; doctors gain access to the
  patients assigned to them when intake/queue features arrive.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.consent import CONSENT_VERSION, consent_text
from app.core.enums import ConsentType, Role, UiLanguage
from app.core.permissions import require_roles
from app.database.models import Patient, User
from app.database.session import get_db
from app.schemas.patient import (
    ConsentDecision,
    ConsentOut,
    ConsentTextOut,
    PatientCreateByStaff,
    PatientList,
    PatientOut,
    PatientRegistered,
    PatientSelfRegister,
    PatientUpdate,
)
from app.schemas.history import HistoryOut, PatientHistoryOut
from app.schemas.user import UserOut
from app.services import (
    audit_service,
    auth_service,
    history_service,
    patient_service,
    user_service,
)

router = APIRouter(tags=["patients"])

patient_only = require_roles(Role.PATIENT)
staff_only = require_roles(Role.STAFF)

_CONSENT_ERRORS = {
    patient_service.ConsentVersionMismatch: (
        status.HTTP_409_CONFLICT,
        "The consent wording has changed. Please read the current version and try again.",
    ),
    patient_service.ConsentRequired: (
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "Consent is required to register.",
    ),
}


def _raise_consent(exc: Exception):
    code, msg = _CONSENT_ERRORS[type(exc)]
    raise HTTPException(status_code=code, detail=msg) from None


@router.get("/consent/current", response_model=ConsentTextOut)
def current_consent(language: UiLanguage = UiLanguage.EN) -> ConsentTextOut:
    title, text = consent_text(ConsentType.DATA_PROCESSING, language)
    return ConsentTextOut(
        consent_type=ConsentType.DATA_PROCESSING, version=CONSENT_VERSION, language=language,
        title=title, text=text, is_draft=CONSENT_VERSION.startswith("draft"),
    )


@router.post("/patients/register", response_model=PatientRegistered,
             status_code=status.HTTP_201_CREATED)
def register(body: PatientSelfRegister, db: Session = Depends(get_db)) -> PatientRegistered:
    try:
        user, patient = patient_service.register_self(db, body)
    except (patient_service.ConsentVersionMismatch, patient_service.ConsentRequired) as e:
        _raise_consent(e)
    except user_service.DuplicateAccountError:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "An account with this mobile number or email already exists. Please log in.") from None
    token, session = auth_service.start_session(db, user)
    return PatientRegistered(access_token=token, expires_at=session.expires_at,
                             user=UserOut.model_validate(user), patient=patient_service.to_out(patient))


# ---- the logged-in patient's own record ----

def _my_patient(user: User = Depends(patient_only), db: Session = Depends(get_db)) -> Patient:
    patient = patient_service.get_for_user(db, user)
    if patient is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No patient profile for this account")
    return patient


@router.get("/patients/me", response_model=PatientOut)
def read_my_profile(patient: Patient = Depends(_my_patient)) -> PatientOut:
    return patient_service.to_out(patient)


@router.patch("/patients/me", response_model=PatientOut)
def update_my_profile(body: PatientUpdate, patient: Patient = Depends(_my_patient),
                      user: User = Depends(patient_only), db: Session = Depends(get_db)) -> PatientOut:
    return patient_service.to_out(patient_service.update(db, patient, body, user))


@router.get("/patients/me/consents", response_model=list[ConsentOut])
def my_consent_history(patient: Patient = Depends(_my_patient)) -> list:
    return patient.consents


@router.post("/patients/me/consents", response_model=ConsentOut, status_code=status.HTTP_201_CREATED)
def record_my_consent(body: ConsentDecision, patient: Patient = Depends(_my_patient),
                      user: User = Depends(patient_only), db: Session = Depends(get_db)):
    try:
        return patient_service.record_consent(db, patient, body, user)
    except patient_service.ConsentVersionMismatch as e:
        _raise_consent(e)


@router.get("/patients/me/history", response_model=PatientHistoryOut)
def my_history(limit: int = Query(10, ge=1, le=50), offset: int = Query(0, ge=0),
               patient: Patient = Depends(_my_patient), db: Session = Depends(get_db)) -> PatientHistoryOut:
    """The logged-in patient's own earlier visits: staff-confirmed information only."""
    return history_service.for_own_account(db, patient.id, limit=limit, offset=offset)


# ---- front-desk staff ----

def _patient_or_404(patient_id: uuid.UUID, db: Session) -> Patient:
    patient = patient_service.get(db, patient_id)
    if patient is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Patient not found")
    return patient


@router.post("/patients", response_model=PatientOut, status_code=status.HTTP_201_CREATED)
def register_walk_in(body: PatientCreateByStaff, staff: User = Depends(staff_only),
                     db: Session = Depends(get_db)) -> PatientOut:
    try:
        return patient_service.to_out(patient_service.register_by_staff(db, body, staff))
    except (patient_service.ConsentVersionMismatch, patient_service.ConsentRequired) as e:
        _raise_consent(e)


@router.get("/patients", response_model=PatientList)
def search_patients(q: str | None = Query(None, max_length=120),
                    limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0),
                    _: User = Depends(staff_only), db: Session = Depends(get_db)) -> PatientList:
    rows, total = patient_service.search(db, q, limit=limit, offset=offset)
    return PatientList(items=[patient_service.to_out(p) for p in rows], total=total)


@router.get("/patients/{patient_id}", response_model=PatientOut)
def read_patient(patient_id: uuid.UUID, staff: User = Depends(staff_only),
                 db: Session = Depends(get_db)) -> PatientOut:
    patient = _patient_or_404(patient_id, db)
    patient_service.audit_view(db, patient, staff)
    return patient_service.to_out(patient)


@router.get("/patients/{patient_id}/history", response_model=HistoryOut)
def patient_history(patient_id: uuid.UUID, limit: int = Query(10, ge=1, le=50), offset: int = Query(0, ge=0),
                    staff: User = Depends(staff_only), db: Session = Depends(get_db)) -> HistoryOut:
    """Earlier encounters of one verified patient (by record id, never by name). Audited."""
    patient = _patient_or_404(patient_id, db)
    audit_service.record(db, "patient.history_viewed", actor_user_id=staff.id, target_type="patient",
                         target_id=patient.id)
    db.commit()
    return history_service.for_patient(db, patient.id, limit=limit, offset=offset)


@router.patch("/patients/{patient_id}", response_model=PatientOut)
def correct_patient(patient_id: uuid.UUID, body: PatientUpdate, staff: User = Depends(staff_only),
                    db: Session = Depends(get_db)) -> PatientOut:
    patient = _patient_or_404(patient_id, db)
    return patient_service.to_out(patient_service.update(db, patient, body, staff))


@router.get("/patients/{patient_id}/consents", response_model=list[ConsentOut])
def patient_consent_history(patient_id: uuid.UUID, _: User = Depends(staff_only),
                            db: Session = Depends(get_db)) -> list:
    return _patient_or_404(patient_id, db).consents


@router.post("/patients/{patient_id}/consents", response_model=ConsentOut,
             status_code=status.HTTP_201_CREATED)
def record_patient_consent(patient_id: uuid.UUID, body: ConsentDecision,
                           staff: User = Depends(staff_only), db: Session = Depends(get_db)):
    patient = _patient_or_404(patient_id, db)
    try:
        return patient_service.record_consent(db, patient, body, staff)
    except patient_service.ConsentVersionMismatch as e:
        _raise_consent(e)
