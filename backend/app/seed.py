"""Create SYNTHETIC demo accounts (never real people).

Run from backend/:   ..\\.venv\\Scripts\\python.exe -m app.seed
Safe to run repeatedly: existing accounts are left unchanged.
Password comes from SEED_DEMO_PASSWORD in the repo-root .env file.
"""

import sys

from app.core.config import get_settings
from app.core.enums import Role, UiLanguage
from app.database.session import SessionLocal
from app.services import user_service

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
    print(f"Done: {created} created.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
