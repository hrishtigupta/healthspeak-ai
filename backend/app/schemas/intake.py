"""Conversation, message and intake shapes."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.enums import (
    ContentLanguage,
    ConversationStatus,
    Gender,
    InputMode,
    MessageSender,
    ReviewStatus,
    TranscriptionStatus,
    TranslationStatus,
)

MAX_MESSAGE_CHARS = 4000
MAX_FINAL_TEXT_CHARS = 20000


def _not_blank(v: str) -> str:
    if not v or not v.strip():
        raise ValueError("Text cannot be empty.")
    return v


class MessageCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Stored exactly as sent (only checked for being non-empty).
    content: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)
    input_mode: InputMode = InputMode.TEXT
    language: ContentLanguage = ContentLanguage.EN
    # Required for input_mode "voice_server": the transcription the patient reviewed.
    transcription_id: uuid.UUID | None = None

    @field_validator("content")
    @classmethod
    def check_content(cls, v: str) -> str:
        return _not_blank(v)

    @model_validator(mode="after")
    def check_transcription(self):
        if (self.input_mode == InputMode.VOICE_SERVER) != (self.transcription_id is not None):
            raise ValueError("transcription_id is required for voice_server messages and only for them.")
        return self


class TranscriptionOut(BaseModel):
    """Machine transcript for the patient to review before sending."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: TranscriptionStatus
    language: ContentLanguage
    text: str | None = Field(validation_alias="transcript_text")
    duration_seconds: float | None
    model_id: str | None
    processing_ms: int | None


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    seq: int
    sender: MessageSender
    input_mode: InputMode
    language: ContentLanguage
    content: str
    created_at: datetime


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: ConversationStatus
    created_at: datetime
    submitted_at: datetime | None
    messages: list[MessageOut]


class MessageExchange(BaseModel):
    """The patient's stored message plus the assistant's acknowledgement."""

    patient_message: MessageOut
    assistant_message: MessageOut


class IntakePatientSummary(BaseModel):
    id: uuid.UUID
    full_name: str
    age: int
    gender: Gender
    preferred_language: ContentLanguage


class IntakeRevisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    field: str
    old_value: str | None
    new_value: str | None
    reason: str | None
    edited_by_user_id: uuid.UUID | None
    created_at: datetime


class IntakeListItem(BaseModel):
    id: uuid.UUID
    patient_id: uuid.UUID
    patient_name: str
    original_language: ContentLanguage
    snippet: str
    translation_status: TranslationStatus
    review_status: ReviewStatus
    created_at: datetime


class IntakeList(BaseModel):
    items: list[IntakeListItem]
    total: int


class IntakeStaffView(BaseModel):
    """Everything staff need to review an intake. Unreviewed text is labelled by review_status."""

    id: uuid.UUID
    patient: IntakePatientSummary
    original_language: ContentLanguage
    original_text: str
    english_text: str | None
    translation_status: TranslationStatus
    translation_model: str | None
    translation_error: str | None
    final_text: str | None
    review_status: ReviewStatus
    reviewed_by_user_id: uuid.UUID | None
    reviewed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    messages: list[MessageOut]
    revisions: list[IntakeRevisionOut]


class IntakePatientView(BaseModel):
    """What a patient sees about their own submission."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    original_language: ContentLanguage
    original_text: str
    review_status: ReviewStatus
    created_at: datetime
    reviewed_at: datetime | None


class IntakeCorrection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    final_text: str = Field(min_length=1, max_length=MAX_FINAL_TEXT_CHARS)
    reason: str | None = Field(default=None, max_length=500)

    @field_validator("final_text")
    @classmethod
    def check_text(cls, v: str) -> str:
        return _not_blank(v)


class IntakeConfirm(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Optional last edit made at the moment of confirming.
    final_text: str | None = Field(default=None, max_length=MAX_FINAL_TEXT_CHARS)
    reason: str | None = Field(default=None, max_length=500)

    @field_validator("final_text")
    @classmethod
    def check_text(cls, v: str | None) -> str | None:
        return _not_blank(v) if v is not None else None
