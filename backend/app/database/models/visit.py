"""D5 Queue and Visit Tokens, D6 Appointments and Doctor Schedules, notifications."""

import uuid
from datetime import date, datetime, time

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    Text,
    Time,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import AppointmentStatus, QueueStatus, sql_in_list
from app.database.base import Base
from app.database.models.department import Department
from app.database.models.mixins import Timestamps, UuidPk
from app.database.models.patient import Patient
from app.database.models.user import User


class QueueCounter(Base):
    """Last token number handed out per department per (local) day."""

    __tablename__ = "queue_counters"
    __table_args__ = (PrimaryKeyConstraint("department_id", "day", name="pk_queue_counters"),)

    department_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("departments.id", ondelete="RESTRICT"))
    day: Mapped[date] = mapped_column(Date)
    last_number: Mapped[int] = mapped_column(Integer)


class QueueEntry(UuidPk, Timestamps, Base):
    __tablename__ = "queue_entries"
    __table_args__ = (
        CheckConstraint(f"status IN ({sql_in_list(QueueStatus)})", name="status_valid"),
        UniqueConstraint("department_id", "day", "token_number", name="uq_queue_entries_token"),
        Index("ix_queue_entries_day_status", "day", "status"),
    )

    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("patients.id", ondelete="RESTRICT"),
                                                  index=True)
    intake_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("intake_records.id", ondelete="RESTRICT"), unique=True)
    department_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("departments.id", ondelete="RESTRICT"))
    doctor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), index=True)
    day: Mapped[date] = mapped_column(Date)  # hospital-local date the token belongs to
    token_number: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default=QueueStatus.WAITING.value)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"))
    checked_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    called_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # cancelled / no-show

    patient: Mapped[Patient] = relationship(lazy="joined")
    department: Mapped[Department] = relationship(lazy="joined")
    doctor: Mapped[User | None] = relationship(foreign_keys=[doctor_user_id], lazy="joined")
    notes: Mapped[list["QueueNote"]] = relationship(back_populates="entry", order_by="QueueNote.created_at",
                                                    lazy="selectin")


class QueueNote(UuidPk, Base):
    """Internal care-team note on a visit (append-only)."""

    __tablename__ = "queue_notes"

    queue_entry_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("queue_entries.id", ondelete="RESTRICT"), index=True)
    author_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"))
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.clock_timestamp(),
                                                 nullable=False)

    entry: Mapped[QueueEntry] = relationship(back_populates="notes")
    author: Mapped[User | None] = relationship(lazy="joined")


class DoctorSchedule(UuidPk, Timestamps, Base):
    """Weekly availability: on `weekday` (0 = Monday) from start to end, in local time."""

    __tablename__ = "doctor_schedules"
    __table_args__ = (
        CheckConstraint("weekday BETWEEN 0 AND 6", name="weekday_range"),
        CheckConstraint("start_time < end_time", name="time_order"),
        CheckConstraint("slot_minutes BETWEEN 5 AND 120", name="slot_range"),
    )

    doctor_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="RESTRICT"),
                                                      index=True)
    department_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("departments.id", ondelete="RESTRICT"))
    weekday: Mapped[int] = mapped_column(Integer)
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    slot_minutes: Mapped[int] = mapped_column(Integer, default=15)
    room: Mapped[str | None] = mapped_column(String(60))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))

    doctor: Mapped[User] = relationship(lazy="joined")
    department: Mapped[Department] = relationship(lazy="joined")


class Appointment(UuidPk, Timestamps, Base):
    __tablename__ = "appointments"
    __table_args__ = (
        CheckConstraint(f"status IN ({sql_in_list(AppointmentStatus)})", name="status_valid"),
        CheckConstraint("starts_at < ends_at", name="time_order"),
        # The database itself refuses two BOOKED appointments for one doctor at one time.
        Index("uq_appointments_doctor_booked_start", "doctor_user_id", "starts_at", unique=True,
              postgresql_where=text("status = 'booked'")),
    )

    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("patients.id", ondelete="RESTRICT"),
                                                  index=True)
    doctor_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="RESTRICT"))
    department_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("departments.id", ondelete="RESTRICT"))
    schedule_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("doctor_schedules.id", ondelete="SET NULL"))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    room: Mapped[str | None] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(16), default=AppointmentStatus.BOOKED.value)
    reason: Mapped[str | None] = mapped_column(String(300))
    cancelled_reason: Mapped[str | None] = mapped_column(String(300))
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"))

    patient: Mapped[Patient] = relationship(lazy="joined")
    doctor: Mapped[User] = relationship(foreign_keys=[doctor_user_id], lazy="joined")
    department: Mapped[Department] = relationship(lazy="joined")


class Notification(UuidPk, Base):
    """In-app message for one user. Keep text short; no clinical details."""

    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_user_unread", "user_id", "read_at"),)

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(120))
    body: Mapped[str] = mapped_column(String(500))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.clock_timestamp(),
                                                 nullable=False)
