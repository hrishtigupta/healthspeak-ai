"""Patient profile and consent shapes."""

import uuid
from datetime import UTC, date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.config import get_settings
from app.core.enums import ConsentMethod, ConsentType, Gender, UiLanguage
from app.core.security import normalize_email, normalize_phone
from app.schemas.user import PASSWORD_MAX_LENGTH, PASSWORD_MIN_LENGTH, UserOut


def _phone(v: str | None, *, required: bool) -> str | None:
    if v is None or not v.strip():
        if required:
            raise ValueError("Mobile number is required.")
        return None
    norm = normalize_phone(v, get_settings().default_phone_country_code)
    if norm is None:
        raise ValueError("Enter a valid phone number (8-15 digits).")
    return norm


def _name(v: str) -> str:
    v = " ".join(v.split())
    if not v:
        raise ValueError("Full name is required.")
    return v


def _dob(v: date) -> date:
    today = datetime.now(UTC).date()
    if v > today:
        raise ValueError("Date of birth cannot be in the future.")
    if v.year < today.year - 130:
        raise ValueError("Date of birth is too far in the past.")
    return v


class ConsentDecision(BaseModel):
    """What the patient agreed to. `version` must match the wording they were shown."""

    model_config = ConfigDict(extra="forbid")

    version: str = Field(min_length=1, max_length=32)
    granted: bool
    language: UiLanguage = UiLanguage.EN


class _PatientFields(BaseModel):
    full_name: str = Field(min_length=1, max_length=120)
    date_of_birth: date
    gender: Gender
    preferred_language: UiLanguage = UiLanguage.EN
    email: EmailStr | None = None

    @field_validator("full_name")
    @classmethod
    def check_name(cls, v: str) -> str:
        return _name(v)

    @field_validator("date_of_birth")
    @classmethod
    def check_dob(cls, v: date) -> date:
        return _dob(v)

    @field_validator("email")
    @classmethod
    def check_email(cls, v):
        return normalize_email(v) if v else None


class PatientSelfRegister(_PatientFields):
    """Public sign-up form: creates a patient login AND profile."""

    model_config = ConfigDict(extra="forbid")

    phone: str = Field(max_length=24)
    password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)
    ui_language: UiLanguage = UiLanguage.EN
    consent: ConsentDecision

    @field_validator("phone")
    @classmethod
    def check_phone(cls, v: str) -> str | None:
        return _phone(v, required=True)


class PatientCreateByStaff(_PatientFields):
    """Walk-in registration at the front desk (no login account)."""

    model_config = ConfigDict(extra="forbid")

    phone: str | None = Field(default=None, max_length=24)
    consent: ConsentDecision

    @field_validator("phone")
    @classmethod
    def check_phone(cls, v: str | None) -> str | None:
        return _phone(v, required=False)


class PatientUpdate(BaseModel):
    """Fields a patient (or staff) may correct. Omitted fields are left unchanged."""

    model_config = ConfigDict(extra="forbid")

    full_name: str | None = Field(default=None, min_length=1, max_length=120)
    date_of_birth: date | None = None
    gender: Gender | None = None
    preferred_language: UiLanguage | None = None

    @field_validator("full_name")
    @classmethod
    def check_name(cls, v):
        return _name(v) if v is not None else v

    @field_validator("date_of_birth")
    @classmethod
    def check_dob(cls, v):
        return _dob(v) if v is not None else v


class ConsentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    consent_type: ConsentType
    version: str
    granted: bool
    method: ConsentMethod
    language: UiLanguage
    created_at: datetime


class ConsentStatus(BaseModel):
    """Latest decision for data-processing consent, and whether it covers current wording."""

    granted: bool
    version: str | None
    is_current_version: bool
    recorded_at: datetime | None


class PhoneChangeRequest(BaseModel):
    """Ask for a code to be sent to a NEW (or not-yet-verified) mobile number."""

    model_config = ConfigDict(extra="forbid")

    phone: str = Field(max_length=24)

    @field_validator("phone")
    @classmethod
    def check_phone(cls, v: str) -> str | None:
        return _phone(v, required=True)


class PhoneChangeConfirm(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=6, max_length=6, pattern=r"^[0-9]{6}$")


class PhoneCodeSent(BaseModel):
    detail: str
    phone: str
    # Only present in development with the console SMS provider (never in production).
    dev_code: str | None = None
    dev_notice: str | None = None


class PatientOut(BaseModel):
    id: uuid.UUID
    full_name: str
    date_of_birth: date
    age: int
    gender: Gender
    phone: str | None
    # True only after the account holder confirmed this number with an SMS code.
    phone_verified: bool = False
    email: str | None
    preferred_language: UiLanguage
    has_account: bool
    consent: ConsentStatus
    created_at: datetime


class PatientList(BaseModel):
    items: list[PatientOut]
    total: int


class PatientRegistered(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: UserOut
    patient: PatientOut


class ConsentTextOut(BaseModel):
    consent_type: ConsentType
    version: str
    language: UiLanguage
    title: str
    text: str
    is_draft: bool
