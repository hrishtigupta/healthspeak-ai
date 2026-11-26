r"""One-time setup of a NEW (e.g. production) database: the first administrator and the
default departments. Unlike app.seed it creates NO demo accounts and needs no demo password.

Run from backend/ against the database in DATABASE_URL:

    ..\.venv\Scripts\python.exe -m app.bootstrap --email you@hospital.example --name "Your Name"

The password is typed at a hidden prompt (never put it on the command line or in a file).
Safe to run twice: it refuses to create a second bootstrap administrator and only loads the
default departments when none exist. The default routing rules are DRAFTS to be reviewed by
clinicians in the admin screen.
"""

import argparse
import getpass
import sys

from sqlalchemy import select

from app.core.enums import Role, UiLanguage
from app.database.models import User
from app.database.session import SessionLocal
from app.schemas.user import PASSWORD_MAX_LENGTH, PASSWORD_MIN_LENGTH
from app.services import department_service, user_service


def bootstrap(db, *, email: str, name: str, password: str) -> dict:
    """Create the first admin (if none exists) and the default departments. Returns what was done."""
    done = {"admin_created": False, "departments_loaded": 0}
    if db.scalar(select(User.id).where(User.role == Role.ADMIN.value).limit(1)):
        done["admin_exists"] = True
    else:
        if not PASSWORD_MIN_LENGTH <= len(password) <= PASSWORD_MAX_LENGTH:
            raise ValueError(f"Password must be {PASSWORD_MIN_LENGTH}-{PASSWORD_MAX_LENGTH} characters.")
        user_service.create_user(db, full_name=name, password=password, role=Role.ADMIN,
                                 email=email, ui_language=UiLanguage.EN)
        done["admin_created"] = True
    done["departments_loaded"] = department_service.load_defaults(db)
    return done


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--email", required=True)
    ap.add_argument("--name", required=True)
    args = ap.parse_args(argv)
    with SessionLocal() as db:
        has_admin = bool(db.scalar(select(User.id).where(User.role == Role.ADMIN.value).limit(1)))
        password = ""
        if not has_admin:
            password = getpass.getpass("Choose the administrator password (hidden): ")
            if password != getpass.getpass("Type it again: "):
                print("The two passwords do not match - nothing was created.")
                return 1
        try:
            done = bootstrap(db, email=args.email, name=args.name, password=password)
        except ValueError as e:
            print(f"Nothing created: {e}")
            return 1
    print("Administrator:", "created" if done["admin_created"] else "already exists (unchanged)")
    print("Default departments:", f"{done['departments_loaded']} routing rules loaded (DRAFT - clinicians must review)"
          if done["departments_loaded"] else "already present (unchanged)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
