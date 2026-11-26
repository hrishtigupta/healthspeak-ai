"""Fill an intake's english_text using the local translation model.

The original text is never modified. If the model is unavailable or fails, the
intake keeps translation_status pending/failed with a visible reason, and staff
can retry or type the English version themselves.
"""

import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.ai.model_loader import EngineUnavailable, translation_slot
from app.core.enums import ContentLanguage, MessageSender, TranslationStatus
from app.database.models import IntakeRecord, User
from app.services import audit_service

logger = logging.getLogger(__name__)


def needs_translation(intake: IntakeRecord) -> bool:
    return intake.translation_status in (TranslationStatus.PENDING.value, TranslationStatus.FAILED.value)


def translate_intake(db: Session, intake: IntakeRecord, actor: User | None) -> IntakeRecord:
    """Translate each non-English patient message and join them in order."""
    if not needs_translation(intake):
        return intake
    patient_msgs = [m for m in intake.conversation.messages if m.sender == MessageSender.PATIENT.value]
    try:
        engine = translation_slot.get()
        parts, model = [], None
        for m in patient_msgs:
            if m.language == ContentLanguage.EN.value:
                parts.append(m.content)
            elif m.english_text:  # already translated while chatting: reuse, do not translate twice
                parts.append(m.english_text)
                model = (m.meta or {}).get("translation_model") or model
            else:
                result = engine.translate(m.content, ContentLanguage(m.language))
                parts.append(result.text)
                model = f"{result.model_id}@{result.model_revision[:10]}"
    except EngineUnavailable as exc:
        intake.translation_status = TranslationStatus.PENDING.value
        intake.translation_error = str(exc)[:200]
        db.commit()
        return intake
    except Exception:  # noqa: BLE001
        logger.exception("Translation failed")
        intake.translation_status = TranslationStatus.FAILED.value
        intake.translation_error = "Translation failed (see server log)."
        db.commit()
        return intake

    intake.english_text = "\n".join(parts)
    intake.translation_status = TranslationStatus.COMPLETED.value
    intake.translation_model = model
    intake.translated_at = datetime.now(UTC)
    intake.translation_error = None
    audit_service.record(db, "intake.translated", actor_user_id=actor.id if actor else None,
                         target_type="intake", target_id=intake.id, details={"model": model})
    db.commit()
    db.refresh(intake)
    from app.services import analysis_service  # local import: avoids an import cycle

    analysis_service.analyse_if_possible(db, intake, actor)
    db.refresh(intake)
    return intake
