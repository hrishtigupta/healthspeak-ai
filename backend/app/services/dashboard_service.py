"""Aggregated counts for dashboards. Totals only: no names or other identifiers."""

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.model_loader import asr_slot, translation_slot
from app.core.clock import local_day_bounds_utc, local_today, now_utc
from app.core.enums import AppointmentStatus, QueueStatus, ReviewStatus
from app.database.models import (
    Appointment,
    AudioTranscription,
    Department,
    IntakeAnalysis,
    IntakeRecord,
    QueueEntry,
    User,
)


def _counts(db: Session, column, *where) -> dict[str, int]:
    rows = db.execute(select(column, func.count()).where(*where).group_by(column)).all()
    return {str(k): v for k, v in rows}


def _queue_counts(db: Session, *where) -> dict[str, int]:
    counts = _counts(db, QueueEntry.status, QueueEntry.day == local_today(), *where)
    return {s.value: counts.get(s.value, 0) for s in QueueStatus}


def _avg_wait_minutes(db: Session, *where) -> float | None:
    secs = db.scalar(select(func.avg(func.extract("epoch", QueueEntry.called_at - QueueEntry.created_at)))
                     .where(QueueEntry.day == local_today(), QueueEntry.called_at.is_not(None), *where))
    return round(float(secs) / 60, 1) if secs is not None else None


def staff(db: Session) -> dict:
    pending = select(IntakeRecord.id).where(IntakeRecord.review_status == ReviewStatus.PENDING_REVIEW.value)
    start, end = local_day_bounds_utc(local_today())
    latest_attention = db.scalar(
        select(func.count(func.distinct(IntakeAnalysis.intake_id))).where(
            IntakeAnalysis.needs_attention.is_(True), IntakeAnalysis.intake_id.in_(pending)))
    return {
        "day": local_today().isoformat(),
        "queue": _queue_counts(db),
        "intakes_pending_review": db.scalar(select(func.count()).select_from(pending.subquery())) or 0,
        "pending_with_attention_flag": latest_attention or 0,
        "appointments_today": db.scalar(select(func.count()).select_from(Appointment).where(
            Appointment.starts_at >= start, Appointment.starts_at < end,
            Appointment.status == AppointmentStatus.BOOKED.value)) or 0,
        "average_wait_minutes": _avg_wait_minutes(db),
    }


def doctor(db: Session, user: User) -> dict:
    start, end = local_day_bounds_utc(local_today())
    return {
        "day": local_today().isoformat(),
        "my_queue": _queue_counts(db, QueueEntry.doctor_user_id == user.id),
        "my_appointments_today": db.scalar(select(func.count()).select_from(Appointment).where(
            Appointment.doctor_user_id == user.id, Appointment.starts_at >= start, Appointment.starts_at < end,
            Appointment.status == AppointmentStatus.BOOKED.value)) or 0,
        "my_average_wait_minutes": _avg_wait_minutes(db, QueueEntry.doctor_user_id == user.id),
    }


def admin(db: Session) -> dict:
    since = now_utc() - timedelta(days=30)
    by_dept = db.execute(
        select(Department.name, func.count()).join(IntakeRecord, IntakeRecord.confirmed_department_id == Department.id)
        .where(IntakeRecord.created_at >= since).group_by(Department.name).order_by(func.count().desc())).all()
    return {
        "day": local_today().isoformat(),
        "users_by_role": _counts(db, User.role, User.is_active.is_(True)),
        "intakes_by_review_status": _counts(db, IntakeRecord.review_status),
        "intakes_last_30_days_by_language": _counts(db, IntakeRecord.original_language,
                                                    IntakeRecord.created_at >= since),
        "confirmed_last_30_days_by_department": {name: n for name, n in by_dept},
        "translation_status": _counts(db, IntakeRecord.translation_status),
        "transcriptions_last_30_days": _counts(db, AudioTranscription.status, AudioTranscription.created_at >= since),
        "queue_today": _queue_counts(db),
        "average_wait_minutes_today": _avg_wait_minutes(db),
        "ai_models": [{"name": s.status().name, "state": s.status().state.value,
                       "model_id": s.status().model_id} for s in (asr_slot, translation_slot)],
    }
