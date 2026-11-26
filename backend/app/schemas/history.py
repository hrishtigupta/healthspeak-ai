"""Shapes for a patient's previous encounters and symptom review."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.enums import ContentLanguage, ReviewStatus, SymptomMatchType, SymptomReviewStatus, SymptomStatus

HISTORY_NOTICE = (
    "Past encounters only. Symptoms, medicines and allergies listed here were reported on the dates "
    "shown and must NOT be assumed to be current. 'AI-extracted' items have not been confirmed by staff."
)


class SymptomOut(BaseModel):
    """A symptom of the CURRENT intake: what the AI found and what staff decided."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    term: str
    symptom_code: str | None
    status: SymptomStatus
    subject: str
    match_type: SymptomMatchType
    evidence_text: str | None
    evidence_start: int | None
    evidence_end: int | None
    attributes: dict
    review_status: SymptomReviewStatus
    confirmed_term: str | None
    confirmed_status: SymptomStatus | None
    review_note: str | None
    reviewed_by_user_id: uuid.UUID | None
    reviewed_at: datetime | None
    effective_term: str
    effective_status: SymptomStatus


class SymptomReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["confirm", "reject", "correct"]
    term: str | None = Field(default=None, min_length=1, max_length=60)
    status: SymptomStatus | None = None
    note: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def check(self):
        if self.action == "correct" and self.term is None and self.status is None:
            raise ValueError("A correction needs a new term and/or status.")
        if self.action != "correct" and (self.term is not None or self.status is not None):
            raise ValueError("term/status can only be given with action 'correct'.")
        return self

    @field_validator("term")
    @classmethod
    def term_not_blank(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("Term cannot be blank.")
        return v


class SymptomAdd(BaseModel):
    model_config = ConfigDict(extra="forbid")

    term: str = Field(min_length=1, max_length=60)
    status: SymptomStatus = SymptomStatus.CURRENT
    evidence_text: str | None = Field(default=None, max_length=500)
    note: str | None = Field(default=None, max_length=500)

    @field_validator("term")
    @classmethod
    def term_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Term cannot be blank.")
        return v


class HistorySymptom(BaseModel):
    term: str
    symptom_code: str | None
    status: SymptomStatus
    # staff_confirmed = a staff member confirmed/corrected it; ai_unconfirmed = AI reading only.
    source: Literal["staff_confirmed", "ai_unconfirmed"]
    evidence_text: str | None = None
    details: dict[str, str] = {}  # e.g. {"duration": "for three days"}, only what was stated


class HistoryEncounter(BaseModel):
    intake_id: uuid.UUID
    encounter_date: datetime
    original_language: ContentLanguage
    review_status: ReviewStatus
    reviewed_at: datetime | None
    confirmed_department: str | None  # chosen by staff
    ai_suggested_department: str | None  # advice only; omitted for patients
    statement: str  # staff-reviewed text if any, else what the patient said (truncated)
    symptoms: list[HistorySymptom]
    # Quoted from what the patient said on that date; not verified, not assumed current.
    medication_mentions: list[str]
    allergy_mentions: list[str]


class PatientEncounterView(BaseModel):
    """What a patient sees of their own past encounters: staff-confirmed facts only."""

    intake_id: uuid.UUID
    encounter_date: datetime
    review_status: ReviewStatus
    confirmed_department: str | None
    statement: str
    confirmed_symptoms: list[HistorySymptom]


class RecurrenceRef(BaseModel):
    intake_id: uuid.UUID
    encounter_date: datetime
    source: Literal["staff_confirmed", "ai_unconfirmed"]
    status: SymptomStatus


class RecurringSymptom(BaseModel):
    term: str
    previous: list[RecurrenceRef]


class HistoryOut(BaseModel):
    patient_id: uuid.UUID
    notice: str = HISTORY_NOTICE
    total: int
    limit: int
    offset: int
    encounters: list[HistoryEncounter]
    # Present-encounter symptoms that also appear in earlier encounters (context only;
    # never changes the department suggestion).
    recurring: list[RecurringSymptom] = []


class PatientHistoryOut(BaseModel):
    notice: str = ("Your previous visits. Only information a staff member has confirmed is shown. "
                   "Past symptoms are not assumed to be current.")
    total: int
    limit: int
    offset: int
    encounters: list[PatientEncounterView]
