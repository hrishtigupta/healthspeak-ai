"""Builds the assistant's reply to a patient's chat message (database + models side).

For each patient message it: (1) gets English text to analyse (Hindi/Urdu are translated with the
local model, with a native-script glossary as a safety net; the original text is never changed),
(2) merges details from answers to earlier questions, (3) runs the existing extractor and routing
rules over the WHOLE conversation so far, and (4) lets the dialogue manager choose the next
question or the preliminary department explanation.
"""

import logging

from sqlalchemy.orm import Session

from app.ai import department_classification, dialogue, text_processing
from app.ai.model_loader import EngineUnavailable, translation_slot
from app.core.config import get_settings
from app.core.enums import ContentLanguage, MessageSender
from app.database.models import Conversation, Message
from app.services import department_service

log = logging.getLogger("healthspeak.dialogue")


def _analysis_text(content: str, lang: str) -> tuple[str, str | None, dict]:
    """(English text used for analysis, real translation or None, info). Never raises."""
    if lang == ContentLanguage.EN.value:
        return content, None, {}
    translation, info = None, {}
    try:
        result = translation_slot.get().translate(content, ContentLanguage(lang))
        translation = result.text
        info["translation_model"] = f"{result.model_id}@{result.model_revision[:10]}"
    except EngineUnavailable as e:
        info["translation"] = "unavailable"
        log.info("Translation unavailable for chat turn: %s", e)
    except Exception:  # noqa: BLE001 - the chat must keep working
        info["translation"] = "failed"
        log.exception("Translation failed for chat turn")
    gloss, hits = dialogue.native_gloss(content, lang)
    return dialogue.merge_analysis_text(translation, gloss, hits), translation, info


def reply_to(db: Session, conv: Conversation, mine: Message) -> tuple[str, dict]:
    """Analyse the new patient message `mine` (not yet committed) and return (reply, meta).

    Fills `mine.english_text` and `mine.meta`. Raises on unexpected errors: the caller falls back
    to a plain acknowledgement so a patient's message is never lost.
    """
    settings = get_settings()
    lang = mine.language
    analysis, translation, info = _analysis_text(mine.content, lang)
    mine.english_text = translation

    prior = sorted(conv.messages, key=lambda m: m.seq)
    last_assistant = next((m for m in reversed(prior) if m.sender == MessageSender.ASSISTANT.value), None)
    asked_slot = (last_assistant.meta or {}).get("asked") if last_assistant else None
    new_details = dialogue.parse_answer(asked_slot, analysis, mine.content, lang)
    mine.meta = {"analysis_text": analysis, "details": new_details, **info}

    texts, details, asked = [], {}, []
    patient_turns = 0
    for m in prior:
        meta = m.meta or {}
        if m.sender == MessageSender.PATIENT.value:
            texts.append(meta.get("analysis_text") or m.english_text or m.content)
            details.update(meta.get("details") or {})
            patient_turns += 1
        elif meta.get("asked"):
            asked.append(meta["asked"])
    texts.append(analysis)
    details.update(new_details)
    patient_turns += 1
    combined = "\n".join(texts)

    default = department_service.default_department(db)
    suggestion = department_classification.suggest(
        combined, department_service.active_rules(db),
        (str(default.id), default.code, default.name) if default else None,
    ).to_dict()
    turn = dialogue.plan_turn(
        lang=lang, combined_en=combined, details=details, asked=asked, suggestion=suggestion,
        patient_turns=patient_turns, emergency_number=settings.emergency_number,
        max_questions=settings.dialogue_max_questions)
    return turn.text, turn.meta


__all__ = ["reply_to", "text_processing"]
