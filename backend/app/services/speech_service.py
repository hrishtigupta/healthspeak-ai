"""Transcribe an uploaded recording with the local speech model."""

import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.ai import audio
from app.ai.model_loader import EngineUnavailable, asr_slot
from app.core.config import get_settings
from app.core.enums import ContentLanguage, ConversationStatus, TranscriptionStatus
from app.database.models import AudioTranscription, Conversation, User
from app.services import audit_service, patient_service

logger = logging.getLogger(__name__)


class ConversationNotOpen(Exception):
    pass


class ConsentMissing(Exception):
    pass


class TranscriptionFailed(Exception):
    """Raised AFTER the failure has been recorded. Message is user-facing."""

    def __init__(self, message: str, status: int):
        super().__init__(message)
        self.status = status


def transcribe_upload(db: Session, conv: Conversation, user: User, data: bytes,
                      content_type: str | None, language: ContentLanguage) -> AudioTranscription:
    if conv.status != ConversationStatus.OPEN.value:
        raise ConversationNotOpen
    if not patient_service.has_valid_consent(conv.patient):
        raise ConsentMissing
    settings = get_settings()
    kind = audio.check_upload(data, content_type, settings)  # raises AudioRejected (nothing stored)

    stored = audio.store(data, kind, settings)
    rec = AudioTranscription(
        conversation_id=conv.id, created_by_user_id=user.id, language=language.value,
        status=TranscriptionStatus.FAILED.value, audio_format=kind, audio_bytes=stored.size,
        audio_sha256=stored.sha256,
    )
    db.add(rec)
    try:
        samples, seconds = audio.decode(stored.path, settings)
        rec.duration_seconds = seconds
        engine = asr_slot.get()
        result = engine.transcribe(samples, language)
    except audio.AudioRejected as exc:
        rec.error_code = exc.code
        _finish(db, rec, stored, settings, user)
        raise
    except EngineUnavailable as exc:
        rec.error_code = "asr_unavailable"
        _finish(db, rec, stored, settings, user)
        raise TranscriptionFailed(f"Voice transcription is unavailable right now. Please type your "
                                  f"concern instead. ({exc})", 503) from None
    except Exception:  # noqa: BLE001 - a model crash must not lose the request silently
        logger.exception("Transcription crashed")
        rec.error_code = "asr_error"
        _finish(db, rec, stored, settings, user)
        raise TranscriptionFailed("Voice transcription failed. Please try again or type instead.",
                                  503) from None

    rec.status = TranscriptionStatus.COMPLETED.value
    rec.transcript_text = result.text
    rec.model_id, rec.model_revision = result.model_id, result.model_revision
    rec.device, rec.processing_ms = result.device, result.processing_ms
    if not result.text:
        rec.status, rec.error_code = TranscriptionStatus.FAILED.value, "no_speech"
        _finish(db, rec, stored, settings, user)
        raise audio.AudioRejected("no_speech", "No words were recognised. Please try again.")
    _finish(db, rec, stored, settings, user)
    return rec


def _finish(db: Session, rec: AudioTranscription, stored, settings, user: User) -> None:
    """Delete the raw audio (unless retention is on), audit, and commit the record."""
    if settings.audio_keep_after_processing:
        rec.audio_path = str(stored.path)
    elif audio.delete(stored.path):
        rec.audio_deleted_at = datetime.now(UTC)
    db.flush()
    audit_service.record(
        db, "audio.transcribed" if rec.status == TranscriptionStatus.COMPLETED.value else "audio.failed",
        actor_user_id=user.id, target_type="transcription", target_id=rec.id,
        details={"error": rec.error_code, "seconds": rec.duration_seconds, "model": rec.model_id},
    )
    db.commit()
    db.refresh(rec)
