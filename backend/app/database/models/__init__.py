"""ORM models. Importing this package registers every table on Base.metadata."""

from app.database.models.audit_event import AuditEvent
from app.database.models.auth_session import AuthSession
from app.database.models.intake import (
    AudioTranscription,
    Conversation,
    IntakeRecord,
    IntakeRevision,
    Message,
)
from app.database.models.patient import ConsentRecord, Patient
from app.database.models.user import User

__all__ = [
    "AudioTranscription", "AuditEvent", "AuthSession", "ConsentRecord", "Conversation", "IntakeRecord",
    "IntakeRevision", "Message", "Patient", "User",
]
