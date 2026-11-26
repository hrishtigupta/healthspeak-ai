"""Builds the assistant's reply to a patient's chat message (database + models side).

For each patient message it: (1) gets English text to analyse (Hindi/Urdu/Dogri are translated with the
local model, with a native-script glossary as a safety net; the original text is never changed),
(2) checks the intent: unsafe / off-topic / service questions get a short redirect and are kept OUT of
the intake, (3) merges details from answers to earlier questions, (4) runs the existing extractor and
routing rules over the WHOLE conversation so far, and (5) lets the dialogue manager choose the next
question or the preliminary department explanation.

Emergency symptoms always win: the guard only acts when the message has no symptom or health word, so
"what is the weather? I have chest pain" is handled as the emergency it is.
"""

import logging

from sqlalchemy.orm import Session

from app.ai import department_classification, dialogue, intent_guard, text_processing
from app.ai.model_loader import EngineUnavailable, translation_slot
from app.core.config import get_settings
from app.core.enums import ContentLanguage, MessageSender
from app.database.models import Conversation, Message
from app.services import department_service

log = logging.getLogger("healthspeak.dialogue")


def counts_for_intake(m: Message) -> bool:
    """False for messages the guard kept out of the intake (greetings, off-topic, unsafe, service)."""
    return not (m.meta or {}).get("skip_intake")


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

    # ---- intent guard (symptoms/health words always mean "health": emergencies are never held back)
    now = text_processing.extract(analysis)
    intent = intent_guard.classify(mine.content, analysis, has_symptoms=bool(now.reported or now.denied))
    if intent.kind in ("unsafe", "unrelated", "service"):
        repeats = sum(1 for m in prior if m.sender == MessageSender.ASSISTANT.value
                      and (m.meta or {}).get("guard") == "unrelated")
        mine.meta = {"analysis_text": "", "details": {}, "skip_intake": True, "guard": intent.kind,
                     "guard_reason": intent.reason, "guard_version": intent_guard.GUARD_VERSION, **info}
        turn = dialogue.guard_turn(kind=intent.kind, lang=lang, emergency_number=settings.emergency_number,
                                   repeats=repeats)
        return turn.text, turn.meta
    greeting = intent.kind == "greeting"

    # the pending question is the last NORMAL assistant message (guard replies do not replace it)
    last_assistant = next((m for m in reversed(prior) if m.sender == MessageSender.ASSISTANT.value
                           and (m.meta or {}).get("stage") != "guard"), None)
    asked_slot = (last_assistant.meta or {}).get("asked") if last_assistant else None
    new_details = {} if greeting else dialogue.parse_answer(asked_slot, analysis, mine.content, lang)
    mine.meta = {"analysis_text": "" if greeting else analysis, "details": new_details,
                 **({"skip_intake": True, "guard": "greeting"} if greeting else {}), **info}

    texts, details, asked = [], {}, []
    patient_turns = 0
    for m in prior:
        meta = m.meta or {}
        if m.sender == MessageSender.PATIENT.value:
            if not counts_for_intake(m):
                continue
            texts.append(meta.get("analysis_text") or m.english_text or m.content)
            details.update(meta.get("details") or {})
            patient_turns += 1
        elif meta.get("asked"):
            asked.append(meta["asked"])
    if not greeting:
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
        max_questions=settings.dialogue_max_questions, greeting=greeting)
    return turn.text, turn.meta


__all__ = ["reply_to", "counts_for_intake", "text_processing"]
