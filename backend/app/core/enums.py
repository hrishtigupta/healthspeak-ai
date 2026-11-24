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


class Gender(StrEnum):
    FEMALE = "female"
    MALE = "male"
    OTHER = "other"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"


class ConsentType(StrEnum):
    # Consent to collect and process the patient's details and described concerns.
    DATA_PROCESSING = "data_processing"


class ConsentMethod(StrEnum):
    SELF_SERVICE = "self_service"  # patient ticked the box themselves
    STAFF_ASSISTED = "staff_assisted"  # staff recorded the patient's verbal/written consent


def sql_in_list(enum_cls: type[StrEnum]) -> str:
    """Render "'a', 'b', 'c'" for use inside a CHECK constraint."""
    return ", ".join(f"'{m.value}'" for m in enum_cls)
