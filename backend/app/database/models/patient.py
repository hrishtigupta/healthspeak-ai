"""D2 Patient Profiles and Consent."""

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import ConsentMethod, ConsentType, Gender, UiLanguage, sql_in_list
from app.database.base import Base
from app.database.models.mixins import Timestamps, UuidPk


class Patient(UuidPk, Timestamps, Base):
    """A person receiving care. May or may not have a login account.

    Walk-in patients registered by staff have user_id = NULL.
    """

    __tablename__ = "patients"
    __table_args__ = (
        CheckConstraint(f"gender IN ({sql_in_list(Gender)})", name="gender_valid"),
        CheckConstraint(
            f"preferred_language IN ({sql_in_list(UiLanguage)})", name="preferred_language_valid"
        ),
    )

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), unique=True
    )
    full_name: Mapped[str] = mapped_column(String(120))
    date_of_birth: Mapped[date] = mapped_column(Date)
    gender: Mapped[str] = mapped_column(String(24))
    # Not unique: family members sometimes share one phone number.
    phone: Mapped[str | None] = mapped_column(String(16), index=True)
    email: Mapped[str | None] = mapped_column(String(254))
    # Language the patient prefers to SPEAK / be spoken to in (not the UI language).
    preferred_language: Mapped[str] = mapped_column(String(8))
    registered_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )

    consents: Mapped[list["ConsentRecord"]] = relationship(
        back_populates="patient", order_by="ConsentRecord.created_at", lazy="selectin"
    )


class ConsentRecord(UuidPk, Base):
    """Append-only consent history. Withdrawal is a new row with granted = false."""

    __tablename__ = "consent_records"
    __table_args__ = (
        CheckConstraint(f"consent_type IN ({sql_in_list(ConsentType)})", name="consent_type_valid"),
        CheckConstraint(f"method IN ({sql_in_list(ConsentMethod)})", name="method_valid"),
        CheckConstraint(f"language IN ({sql_in_list(UiLanguage)})", name="language_valid"),
        Index("ix_consent_records_patient_type_created", "patient_id", "consent_type", "created_at"),
    )

    patient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("patients.id", ondelete="RESTRICT")
    )
    consent_type: Mapped[str] = mapped_column(String(32))
    version: Mapped[str] = mapped_column(String(32))
    granted: Mapped[bool] = mapped_column(Boolean)
    method: Mapped[str] = mapped_column(String(16))
    # Language the consent text was shown in.
    language: Mapped[str] = mapped_column(String(8))
    recorded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    patient: Mapped[Patient] = relationship(back_populates="consents")
