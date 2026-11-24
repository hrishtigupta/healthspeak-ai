"""D3 Conversations and Transcripts, D4 Intake Records.

Text separation rules (from the project brief):
- original_text   exactly what the patient typed/approved — never overwritten
- english_text    English version used by processing (copy if already English,
                  otherwise produced by translation in a later phase)
- final_text      the staff-reviewed version; every change is kept in intake_revisions
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import (
    ContentLanguage,
    ConversationStatus,
    InputMode,
    MessageSender,
    ReviewStatus,
    TranslationStatus,
    sql_in_list,
)
from app.database.base import Base
from app.database.models.mixins import Timestamps, UuidPk
from app.database.models.patient import Patient


class Conversation(UuidPk, Timestamps, Base):
    __tablename__ = "conversations"
    __table_args__ = (
        CheckConstraint(f"status IN ({sql_in_list(ConversationStatus)})", name="status_valid"),
    )

    patient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("patients.id", ondelete="RESTRICT"), index=True
    )
    started_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(16), default=ConversationStatus.OPEN.value)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    patient: Mapped[Patient] = relationship()
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", order_by="Message.seq", lazy="selectin"
    )


class Message(UuidPk, Base):
    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint(f"sender IN ({sql_in_list(MessageSender)})", name="sender_valid"),
        CheckConstraint(f"input_mode IN ({sql_in_list(InputMode)})", name="input_mode_valid"),
        CheckConstraint(f"language IN ({sql_in_list(ContentLanguage)})", name="language_valid"),
        UniqueConstraint("conversation_id", "seq", name="uq_messages_conversation_seq"),
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("conversations.id", ondelete="CASCADE")
    )
    # Position in the conversation (1, 2, 3...): exact order, independent of clock precision.
    seq: Mapped[int] = mapped_column(Integer)
    sender: Mapped[str] = mapped_column(String(16))
    input_mode: Mapped[str] = mapped_column(String(16))
    language: Mapped[str] = mapped_column(String(8))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp(), nullable=False
    )

    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class IntakeRecord(UuidPk, Timestamps, Base):
    __tablename__ = "intake_records"
    __table_args__ = (
        CheckConstraint(f"original_language IN ({sql_in_list(ContentLanguage)})",
                        name="original_language_valid"),
        CheckConstraint(f"translation_status IN ({sql_in_list(TranslationStatus)})",
                        name="translation_status_valid"),
        CheckConstraint(f"review_status IN ({sql_in_list(ReviewStatus)})", name="review_status_valid"),
        Index("ix_intake_records_review_created", "review_status", "created_at"),
    )

    patient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("patients.id", ondelete="RESTRICT"), index=True
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("conversations.id", ondelete="RESTRICT"), unique=True
    )
    original_language: Mapped[str] = mapped_column(String(8))
    original_text: Mapped[str] = mapped_column(Text)
    english_text: Mapped[str | None] = mapped_column(Text)
    translation_status: Mapped[str] = mapped_column(String(16))
    final_text: Mapped[str | None] = mapped_column(Text)
    review_status: Mapped[str] = mapped_column(String(16), default=ReviewStatus.PENDING_REVIEW.value)
    submitted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    patient: Mapped[Patient] = relationship()
    conversation: Mapped[Conversation] = relationship()
    revisions: Mapped[list["IntakeRevision"]] = relationship(
        back_populates="intake", order_by="IntakeRevision.created_at", lazy="selectin"
    )


class IntakeRevision(UuidPk, Base):
    """One staff change to an intake (old and new value kept side by side)."""

    __tablename__ = "intake_revisions"

    intake_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("intake_records.id", ondelete="RESTRICT"), index=True
    )
    field: Mapped[str] = mapped_column(String(32))
    old_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(String(500))
    edited_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp(), nullable=False
    )

    intake: Mapped[IntakeRecord] = relationship(back_populates="revisions")
