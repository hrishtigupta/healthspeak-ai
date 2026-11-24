"""Kiosk registry, heartbeats and overall system health (D8)."""

import shutil
from datetime import timedelta

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.ai import audio
from app.ai.model_loader import asr_slot, translation_slot
from app.core.clock import now_utc
from app.core.config import get_settings
from app.core.enums import TranscriptionStatus, TranslationStatus
from app.core.security import hash_token, new_session_token
from app.database.models import AudioTranscription, IntakeRecord, Kiosk, User
from app.services import audit_service

ONLINE_WITHIN = timedelta(minutes=3)  # heartbeats arrive every minute


class DuplicateCode(Exception):
    pass


def is_online(k: Kiosk) -> bool:
    return bool(k.is_active and k.last_seen_at and now_utc() - k.last_seen_at <= ONLINE_WITHIN)


def register(db: Session, *, code: str, name: str, location: str | None, actor: User) -> tuple[Kiosk, str]:
    """Create a kiosk. Returns (kiosk, plain key) - the key is shown only this once."""
    if db.scalar(select(Kiosk).where(Kiosk.code == code)):
        raise DuplicateCode
    key = new_session_token()
    k = Kiosk(code=code, name=name, location=location, key_hash=hash_token(key), created_by_user_id=actor.id)
    db.add(k)
    db.flush()
    audit_service.record(db, "kiosk.registered", actor_user_id=actor.id, target_type="kiosk", target_id=k.id,
                         details={"code": code})
    db.commit()
    db.refresh(k)
    return k, key


def rotate_key(db: Session, k: Kiosk, actor: User) -> str:
    key = new_session_token()
    k.key_hash = hash_token(key)
    audit_service.record(db, "kiosk.key_rotated", actor_user_id=actor.id, target_type="kiosk", target_id=k.id)
    db.commit()
    return key


def update(db: Session, k: Kiosk, changes: dict, actor: User) -> Kiosk:
    for field, value in changes.items():
        setattr(k, field, value)
    audit_service.record(db, "kiosk.updated", actor_user_id=actor.id, target_type="kiosk", target_id=k.id,
                         details={"fields": sorted(changes)})
    db.commit()
    db.refresh(k)
    return k


def heartbeat(db: Session, key: str, *, app_version: str | None, report: dict) -> Kiosk | None:
    k = db.scalar(select(Kiosk).where(Kiosk.key_hash == hash_token(key)))
    if k is None or not k.is_active:
        return None
    k.last_seen_at = now_utc()
    k.app_version = app_version
    k.last_report = report
    db.commit()
    return k


def list_kiosks(db: Session) -> list[Kiosk]:
    return list(db.scalars(select(Kiosk).order_by(Kiosk.code)))


def system_health(db: Session) -> dict:
    s = get_settings()
    try:
        db.execute(text("SELECT 1"))
        database = "ok"
    except Exception:  # noqa: BLE001
        database = "unavailable"
    since = now_utc() - timedelta(hours=24)
    try:
        folder = audio.storage_dir(s)
        free_gb = round(shutil.disk_usage(folder).free / 1e9, 1)
        writable = True
    except OSError:
        free_gb, writable = None, False
    kiosks = list_kiosks(db)
    return {
        "checked_at": now_utc().isoformat(),
        "database": database,
        "ai_enabled": s.ai_enabled,
        "ffmpeg_available": audio.ffmpeg_available(s),
        "audio_storage": {"writable": writable, "free_gb": free_gb,
                          "keeps_raw_audio": s.audio_keep_after_processing},
        "models": [{"name": st.name, "model_id": st.model_id, "state": st.state.value, "detail": st.detail}
                   for st in (asr_slot.status(), translation_slot.status())],
        "failures_last_24h": {
            "transcriptions_failed": db.scalar(select(func.count()).select_from(AudioTranscription).where(
                AudioTranscription.status == TranscriptionStatus.FAILED.value,
                AudioTranscription.created_at >= since)) or 0,
            "intakes_translation_failed": db.scalar(select(func.count()).select_from(IntakeRecord).where(
                IntakeRecord.translation_status == TranslationStatus.FAILED.value)) or 0,
            "intakes_translation_pending": db.scalar(select(func.count()).select_from(IntakeRecord).where(
                IntakeRecord.translation_status == TranslationStatus.PENDING.value)) or 0,
        },
        "kiosks": {"total": len(kiosks), "online": sum(1 for k in kiosks if is_online(k)),
                   "inactive": sum(1 for k in kiosks if not k.is_active)},
    }
