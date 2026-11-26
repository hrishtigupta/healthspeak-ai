"""Patient conversations, intake submission and staff review.

Safety: the assistant only acknowledges messages with fixed text. It never
interprets symptoms, diagnoses or advises; staff review every intake.
"""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.enums import (
    ContentLanguage,
    ConversationStatus,
    InputMode,
    IntakePriority,
    MessageSender,
    ReviewStatus,
    TranslationStatus,
)
from app.database.models import (
    AudioTranscription,
    Conversation,
    IntakeRecord,
    IntakeRevision,
    Message,
    Patient,
    User,
)
from app.schemas.history import SymptomOut
from app.schemas.intake import (
    AnalysisOut,
    DepartmentRef,
    IntakeList,
    IntakeListItem,
    IntakePatientSummary,
    IntakeStaffView,
    IntakeRevisionOut,
    MessageCreate,
    MessageOut,
)
from app.services import (
    analysis_service,
    audit_service,
    department_service,
    dialogue_service,
    evidence,
    notification_service,
    patient_service,
    priority_service,
    queue_service,
    symptom_service,
    translation_service,
)

MAX_PATIENT_MESSAGES = 50
logger = logging.getLogger(__name__)

ACKNOWLEDGEMENTS = {
    ContentLanguage.EN: (
        "Thank you. Your message has been added to your intake for review by the medical "
        "staff. You can add more details, or end the chat when you are done."
    ),
    ContentLanguage.HI: (
        "धन्यवाद। आपका संदेश चिकित्सा कर्मचारियों की समीक्षा के लिए आपकी इनटेक जानकारी में "
        "जोड़ दिया गया है। आप और जानकारी जोड़ सकते हैं, या पूरा होने पर चैट समाप्त कर सकते हैं।"
    ),
    # DRAFT Dogri wording (Devanagari): needs review by a fluent Dogri speaker.
    ContentLanguage.DOI: (
        "धन्नवाद। तुंदा संदेश मेडिकल स्टाफ दी समीक्षा आस्तै तुंदी इनटेक जानकारी च जोड़ोई गेआ ऐ। "
        "तुस होर जानकारी जोड़ी सकदे ओ, जां पूरा होने पर चैट खत्म करी सकदे ओ।"
    ),
    ContentLanguage.UR: (
        "شکریہ۔ آپ کا پیغام طبی عملے کے جائزے کے لیے آپ کی انٹیک معلومات میں شامل کر دیا گیا "
        "ہے۔ آپ مزید تفصیلات شامل کر سکتے ہیں، یا مکمل ہونے پر چیٹ ختم کر سکتے ہیں۔"
    ),
}


class ConsentMissing(Exception):
    """The patient has no valid (current, granted) consent."""


class ConversationClosed(Exception):
    pass


class TooManyMessages(Exception):
    pass


class NothingToSubmit(Exception):
    pass


class AlreadyConfirmed(Exception):
    pass


class InvalidTranscription(Exception):
    """transcription_id is unknown, from another conversation, failed, or already used."""


class UnknownDepartment(Exception):
    """Confirmation needs an existing, active department."""


class EnglishTextNeeded(Exception):
    """Cannot confirm without an English version (translation not available yet)."""


def _now() -> datetime:
    return datetime.now(UTC)


# ---------- conversations (patient side) ----------

def open_conversation(db: Session, patient: Patient, user: User) -> tuple[Conversation, bool]:
    """Return the patient's open conversation, creating one if needed. (conv, created)."""
    if not patient_service.has_valid_consent(patient):
        raise ConsentMissing
    # Two requests can arrive together (e.g. the chat page opening twice). Lock this patient's row so the
    # second request waits and then finds the conversation the first one created, instead of creating
    # a second open conversation that would split the chat in two.
    db.execute(select(Patient.id).where(Patient.id == patient.id).with_for_update())
    existing = db.scalar(
        select(Conversation).where(Conversation.patient_id == patient.id,
                                   Conversation.status == ConversationStatus.OPEN.value)
        .order_by(Conversation.created_at).limit(1)
    )
    if existing:
        return existing, False
    conv = Conversation(patient_id=patient.id, started_by_user_id=user.id,
                        status=ConversationStatus.OPEN.value)
    db.add(conv)
    db.flush()
    audit_service.record(db, "conversation.started", actor_user_id=user.id,
                         target_type="conversation", target_id=conv.id)
    db.commit()
    db.refresh(conv)
    return conv, True


def get_own_conversation(db: Session, conv_id: uuid.UUID, patient: Patient) -> Conversation | None:
    conv = db.get(Conversation, conv_id)
    return conv if conv is not None and conv.patient_id == patient.id else None


def add_message(db: Session, conv: Conversation, data: MessageCreate) -> tuple[Message, Message]:
    if conv.status != ConversationStatus.OPEN.value:
        raise ConversationClosed
    if not patient_service.has_valid_consent(conv.patient):
        raise ConsentMissing
    patient_count = sum(1 for m in conv.messages if m.sender == MessageSender.PATIENT.value)
    if patient_count >= MAX_PATIENT_MESSAGES:
        raise TooManyMessages
    transcription = None
    if data.transcription_id is not None:
        transcription = db.get(AudioTranscription, data.transcription_id)
        if (transcription is None or transcription.conversation_id != conv.id
                or transcription.status != "completed" or transcription.message_id is not None):
            raise InvalidTranscription
    seq = len(conv.messages)
    mine = Message(conversation=conv, seq=seq + 1, sender=MessageSender.PATIENT.value,
                   input_mode=data.input_mode.value, language=data.language.value,
                   content=data.content)
    try:
        reply_text, reply_meta = dialogue_service.reply_to(db, conv, mine)
    except Exception:  # noqa: BLE001 - never lose the patient's message because analysis failed
        logger.exception("Dialogue reply failed; using the plain acknowledgement")
        reply_text, reply_meta = ACKNOWLEDGEMENTS[data.language], {"stage": "fallback"}
    ack = Message(conversation=conv, seq=seq + 2, sender=MessageSender.ASSISTANT.value,
                  input_mode=InputMode.TEXT.value, language=data.language.value,
                  content=reply_text, meta=reply_meta)
    db.add_all([mine, ack])
    conv.updated_at = _now()
    if transcription is not None:
        db.flush()
        transcription.message_id = mine.id  # raw transcript stays on the transcription row
    db.commit()
    db.refresh(mine)
    db.refresh(ack)
    return mine, ack


def submit(db: Session, conv: Conversation, user: User) -> IntakeRecord:
    """Turn the conversation's patient messages into an intake awaiting staff review."""
    if conv.status != ConversationStatus.OPEN.value:
        raise ConversationClosed
    # Greetings, off-topic and unsafe messages stay in the chat log but never become part of the intake.
    patient_msgs = [m for m in conv.messages if m.sender == MessageSender.PATIENT.value
                    and dialogue_service.counts_for_intake(m)]
    if not patient_msgs:
        raise NothingToSubmit
    original_text = "\n".join(m.content for m in patient_msgs)
    languages = {m.language for m in patient_msgs}
    all_english = languages == {ContentLanguage.EN.value}
    intake = IntakeRecord(
        patient_id=conv.patient_id,
        conversation_id=conv.id,
        original_language=patient_msgs[0].language,
        original_text=original_text,
        # English needs no translation: the English text is the original, unchanged.
        english_text=original_text if all_english else None,
        translation_status=(TranslationStatus.NOT_NEEDED if all_english
                            else TranslationStatus.PENDING).value,
        review_status=ReviewStatus.PENDING_REVIEW.value,
        submitted_by_user_id=user.id,
    )
    priority_service.raise_if_urgent(intake, from_chat=priority_service.chat_was_urgent(conv))
    conv.status = ConversationStatus.SUBMITTED.value
    conv.submitted_at = _now()
    db.add(intake)
    db.flush()
    audit_service.record(db, "intake.submitted", actor_user_id=user.id, target_type="intake",
                         target_id=intake.id, details={"messages": len(patient_msgs),
                                                       "languages": sorted(languages)})
    db.commit()
    db.refresh(intake)
    # Translate Hindi/Urdu now if the local model is available. Failure never loses
    # the submission: the intake stays saved with a visible translation status.
    if translation_service.needs_translation(intake):
        translation_service.translate_intake(db, intake, user)  # analyses on success
    else:
        analysis_service.analyse_if_possible(db, intake, user)
    return intake


def list_for_patient(db: Session, patient: Patient) -> list[IntakeRecord]:
    return list(db.scalars(select(IntakeRecord).where(IntakeRecord.patient_id == patient.id)
                           .order_by(IntakeRecord.created_at.desc())))


# ---------- staff review ----------

def get(db: Session, intake_id: uuid.UUID) -> IntakeRecord | None:
    return db.get(IntakeRecord, intake_id)


def list_for_staff(db: Session, *, review_status: ReviewStatus | None, limit: int,
                   offset: int) -> IntakeList:
    stmt = select(IntakeRecord, Patient.full_name).join(Patient, Patient.id == IntakeRecord.patient_id)
    count = select(func.count()).select_from(IntakeRecord)
    if review_status:
        stmt = stmt.where(IntakeRecord.review_status == review_status.value)
        count = count.where(IntakeRecord.review_status == review_status.value)
    # Urgent first, then oldest first (patients who have waited longest are reviewed first).
    rows = db.execute(stmt.order_by((IntakeRecord.priority == IntakePriority.URGENT.value).desc(),
                                    IntakeRecord.created_at, IntakeRecord.id).limit(limit).offset(offset))
    items = []
    for i, name in rows:
        a = analysis_service.latest(i)
        items.append(IntakeListItem(
            id=i.id, patient_id=i.patient_id, patient_name=name,
            original_language=i.original_language,
            snippet=(i.original_text[:140] + "…") if len(i.original_text) > 140 else i.original_text,
            translation_status=i.translation_status, review_status=i.review_status,
            created_at=i.created_at,
            suggested_department=(a.suggestion.get("department_name") if a else None),
            needs_attention=bool(a and a.needs_attention),
            priority=i.priority, priority_source=i.priority_source,
        ))
    return IntakeList(items=items, total=db.scalar(count) or 0)


def staff_view(db: Session, intake: IntakeRecord, staff: User) -> IntakeStaffView:
    audit_service.record(db, "intake.viewed", actor_user_id=staff.id, target_type="intake",
                         target_id=intake.id)
    db.commit()
    p = intake.patient
    symptom_rows = symptom_service.for_intake(db, intake.id)
    return IntakeStaffView(
        id=intake.id,
        patient=IntakePatientSummary(id=p.id, full_name=p.full_name,
                                     age=patient_service.to_out(p).age, gender=p.gender,
                                     preferred_language=p.preferred_language),
        original_language=intake.original_language, original_text=intake.original_text,
        english_text=intake.english_text, translation_status=intake.translation_status,
        translation_model=intake.translation_model, translation_error=intake.translation_error,
        final_text=intake.final_text, review_status=intake.review_status,
        reviewed_by_user_id=intake.reviewed_by_user_id, reviewed_at=intake.reviewed_at,
        created_at=intake.created_at, updated_at=intake.updated_at,
        messages=[MessageOut.model_validate(m) for m in intake.conversation.messages],
        revisions=[IntakeRevisionOut.model_validate(r) for r in intake.revisions],
        analysis=(AnalysisOut.model_validate(a) if (a := analysis_service.latest(intake)) else None),
        confirmed_department=(DepartmentRef.model_validate(intake.confirmed_department)
                              if intake.confirmed_department else None),
        symptoms=[SymptomOut.model_validate(s) for s in symptom_rows],
        field_evidence=evidence.field_evidence(
            symptoms=symptom_rows, analysis=analysis_service.latest(intake),
            translation_status=intake.translation_status, confirmed_department=intake.confirmed_department),
        priority=intake.priority, priority_source=intake.priority_source,
        priority_reason=intake.priority_reason, priority_changed_at=intake.priority_changed_at,
        priority_changed_by_user_id=intake.priority_changed_by_user_id,
    )


def _revise(db: Session, intake: IntakeRecord, field: str, old, new, reason, staff: User) -> None:
    db.add(IntakeRevision(intake=intake, field=field, old_value=old, new_value=new,
                          reason=reason, edited_by_user_id=staff.id))


def correct(db: Session, intake: IntakeRecord, staff: User, final_text: str,
            reason: str | None) -> IntakeRecord:
    """Set the staff-reviewed text. The previous value is kept in intake_revisions."""
    if final_text != intake.final_text:
        _revise(db, intake, "final_text", intake.final_text, final_text, reason, staff)
        intake.final_text = final_text
        audit_service.record(db, "intake.corrected", actor_user_id=staff.id,
                             target_type="intake", target_id=intake.id)
        db.commit()
        db.refresh(intake)
    return intake


def confirm(db: Session, intake: IntakeRecord, staff: User, final_text: str | None,
            reason: str | None, department_id: uuid.UUID) -> IntakeRecord:
    if intake.review_status == ReviewStatus.CONFIRMED.value:
        raise AlreadyConfirmed
    department = department_service.get_active(db, department_id)
    if department is None:
        raise UnknownDepartment
    if final_text is not None and final_text != intake.final_text:
        _revise(db, intake, "final_text", intake.final_text, final_text, reason, staff)
        intake.final_text = final_text
    if not intake.final_text:
        if not intake.english_text:
            raise EnglishTextNeeded
        _revise(db, intake, "final_text", None, intake.english_text, "accepted as submitted", staff)
        intake.final_text = intake.english_text
    old_dept = intake.confirmed_department.name if intake.confirmed_department else None
    _revise(db, intake, "department", old_dept, department.name, reason, staff)
    intake.confirmed_department_id = department.id
    _revise(db, intake, "review_status", intake.review_status, ReviewStatus.CONFIRMED.value,
            reason, staff)
    intake.review_status = ReviewStatus.CONFIRMED.value
    intake.reviewed_by_user_id = staff.id
    intake.reviewed_at = _now()
    latest = analysis_service.latest(intake)
    suggested = latest.suggestion.get("department_code") if latest else None
    audit_service.record(db, "intake.confirmed", actor_user_id=staff.id, target_type="intake",
                         target_id=intake.id,
                         details={"department": department.code, "suggested": suggested,
                                  "followed_suggestion": suggested == department.code})
    # Same transaction: confirming routes the patient into the department's queue
    # (unless they already have an active visit today).
    try:
        queue_service.create_entry(db, patient=intake.patient, department=department, actor=staff,
                                   intake=intake, commit=False)
    except queue_service.AlreadyQueued:
        pass
    notification_service.notify(db, intake.patient.user_id, "intake.confirmed", "Your concern was reviewed",
                                f"Medical staff reviewed what you shared. Department: {department.name}.")
    db.commit()
    db.refresh(intake)
    return intake
