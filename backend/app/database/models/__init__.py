"""ORM models. Importing this package registers every table on Base.metadata."""

from app.database.models.audit_event import AuditEvent
from app.database.models.auth_session import AuthSession
from app.database.models.department import Department, RoutingRule
from app.database.models.intake import (
    AudioTranscription,
    Conversation,
    IntakeAnalysis,
    IntakeRecord,
    IntakeRevision,
    Message,
)
from app.database.models.patient import ConsentRecord, Patient
from app.database.models.user import User
from app.database.models.visit import (
    Appointment,
    DoctorSchedule,
    Notification,
    QueueCounter,
    QueueEntry,
    QueueNote,
)

__all__ = [
    "AudioTranscription", "AuditEvent", "AuthSession", "ConsentRecord", "Conversation", "Department",
    "IntakeAnalysis", "IntakeRecord", "RoutingRule",
    "IntakeRevision", "Message", "Patient", "User",
    "Appointment", "DoctorSchedule", "Notification", "QueueCounter", "QueueEntry", "QueueNote",
]
