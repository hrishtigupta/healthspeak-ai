"""Fixed value lists shared by models, schemas and permission checks.

The database enforces the same lists with CHECK constraints, so a typo can never
be stored. Add a value here AND in a new migration when extending a list.
"""

from enum import StrEnum


class Role(StrEnum):
    PATIENT = "patient"
    DOCTOR = "doctor"
    STAFF = "staff"  # front-desk / medical staff
    ADMIN = "admin"  # hospital administrator


class UiLanguage(StrEnum):
    """Language used to DISPLAY the app to one user (not the spoken-audio language)."""

    EN = "en"
    HI = "hi"
    UR = "ur"


def sql_in_list(enum_cls: type[StrEnum]) -> str:
    """Render "'a', 'b', 'c'" for use inside a CHECK constraint."""
    return ", ".join(f"'{m.value}'" for m in enum_cls)
