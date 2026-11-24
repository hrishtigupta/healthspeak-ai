"""Create SYNTHETIC demo accounts (never real people).

Run from backend/:   ..\\.venv\\Scripts\\python.exe -m app.seed
Safe to run repeatedly: existing accounts are left unchanged.
Password comes from SEED_DEMO_PASSWORD in the repo-root .env file.
"""

import sys
from datetime import date

from sqlalchemy import select

from app.core.config import get_settings
from app.core.consent import CONSENT_VERSION
from app.core.enums import ConsentMethod, ConsentType, Gender, Role, UiLanguage
from app.database.models import ConsentRecord, Patient, User
from app.database.session import SessionLocal
from app.services import department_service, user_service

# Synthetic profile for the demo patient account, so the intake flow can be tried.
DEMO_PATIENT_PROFILE = {"date_of_birth": date(1990, 1, 15), "gender": Gender.FEMALE}


def _ensure_demo_patient_profile(db, email: str) -> bool:
    user = db.scalar(select(User).where(User.email == email))
    if user is None or db.scalar(select(Patient).where(Patient.user_id == user.id)):
        return False
    patient = Patient(
        user_id=user.id, full_name=user.full_name, phone=user.phone, email=user.email,
        date_of_birth=DEMO_PATIENT_PROFILE["date_of_birth"],
        gender=DEMO_PATIENT_PROFILE["gender"].value,
        preferred_language=user.ui_language, registered_by_user_id=user.id,
    )
    db.add(patient)
    db.flush()
    db.add(ConsentRecord(
        patient_id=patient.id, consent_type=ConsentType.DATA_PROCESSING.value,
        version=CONSENT_VERSION, granted=True, method=ConsentMethod.SELF_SERVICE.value,
        language=user.ui_language, recorded_by_user_id=user.id,
    ))
    db.commit()
    return True

DEMO_USERS = [
    # (email, phone, full name, role, ui_language)
    ("patient@example.com", "+919000000001", "Demo Patient", Role.PATIENT, UiLanguage.HI),
    ("doctor@example.com", "+919000000002", "Dr. Demo Doctor", Role.DOCTOR, UiLanguage.EN),
    ("staff@example.com", "+919000000003", "Demo Reception Staff", Role.STAFF, UiLanguage.EN),
    ("admin@example.com", "+919000000004", "Demo Administrator", Role.ADMIN, UiLanguage.EN),
]


def main() -> int:
    password = get_settings().seed_demo_password
    if not password or len(password) < 8:
        print("SEED_DEMO_PASSWORD is missing or shorter than 8 characters in .env - nothing created.")
        return 1
    created = 0
    with SessionLocal() as db:
        for email, phone, name, role, lang in DEMO_USERS:
            if user_service.contact_in_use(db, email, phone):
                print(f"  exists   {role.value:<8} {email}")
                continue
            user_service.create_user(
                db, full_name=name, password=password, role=role,
                email=email, phone=phone, ui_language=lang,
            )
            created += 1
            print(f"  created  {role.value:<8} {email}")
        if _ensure_demo_patient_profile(db, "patient@example.com"):
            print("  created  patient profile + consent for patient@example.com")
        rules = department_service.load_defaults(db)
        if rules:
            print(f"  created  default departments and {rules} routing rules (DRAFT - review with clinicians)")
    print(f"Done: {created} accounts created.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
