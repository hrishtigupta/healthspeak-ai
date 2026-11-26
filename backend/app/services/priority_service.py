"""Saved Urgent / Normal priority of an intake record.

Rules (no new medical criteria; the emergency rules are the existing ones in app.ai.urgency):
- URGENT when the chat already gave emergency guidance (any assistant message with meta.urgent), or when
  the stored analysis shows a red-flag symptom / hospital "attention" rule on a current mention.
- NORMAL otherwise.
- The system can only RAISE the priority. A department suggestion or a later re-analysis never lowers it.
- Only a staff member can change it (either way), with a required reason. That is recorded as a
  revision and an audit event, and from then on the system no longer touches it.
"""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.ai import urgency
from app.core.enums import IntakePriority, MessageSender, PrioritySource
from app.database.models import IntakeAnalysis, IntakeRecord, IntakeRevision, User
from app.services import audit_service


class PriorityUnchanged(Exception):
    pass


def chat_was_urgent(conversation) -> bool:
    """True if the assistant gave emergency guidance at any point of this conversation."""
    return any(m.sender == MessageSender.ASSISTANT.value and (m.meta or {}).get("urgent")
               for m in conversation.messages)


def analysis_is_urgent(analysis: IntakeAnalysis | None) -> bool:
    if analysis is None:
        return False
    reported = [s.get("term") for s in (analysis.extraction or {}).get("reported", [])
                if isinstance(s, dict) and s.get("status") in ("current", "uncertain")]
    return urgency.is_urgent(reported, (analysis.suggestion or {}).get("attention"))


def raise_if_urgent(intake: IntakeRecord, *, from_chat: bool = False,
                    analysis: IntakeAnalysis | None = None) -> bool:
    """Set URGENT if the rules say so. Never lowers, never touches a staff-set priority."""
    if intake.priority_source == PrioritySource.STAFF.value:
        return False
    if intake.priority == IntakePriority.URGENT.value:
        return False
    if from_chat or analysis_is_urgent(analysis):
        intake.priority = IntakePriority.URGENT.value
        intake.priority_source = PrioritySource.SYSTEM.value
        intake.priority_reason = ("Emergency guidance was shown in the chat." if from_chat
                                  else "An emergency symptom or hospital attention rule matched.")
        intake.priority_changed_at = datetime.now(UTC)
        return True
    return False


def set_by_staff(db: Session, intake: IntakeRecord, staff: User, priority: IntakePriority,
                 reason: str) -> IntakeRecord:
    """A staff member sets the priority (the reason is required and kept)."""
    if intake.priority == priority.value and intake.priority_source == PrioritySource.STAFF.value:
        raise PriorityUnchanged
    old = intake.priority
    db.add(IntakeRevision(intake=intake, field="priority", old_value=old, new_value=priority.value,
                          reason=reason, edited_by_user_id=staff.id))
    intake.priority = priority.value
    intake.priority_source = PrioritySource.STAFF.value
    intake.priority_reason = reason
    intake.priority_changed_by_user_id = staff.id
    intake.priority_changed_at = datetime.now(UTC)
    audit_service.record(db, "intake.priority_changed", actor_user_id=staff.id, target_type="intake",
                         target_id=intake.id, details={"from": old, "to": priority.value})
    db.commit()
    db.refresh(intake)
    return intake
