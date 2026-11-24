"""Status of the local AI models (D8 Kiosk and Voice AI Status, model part)."""

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.ai import audio
from app.ai.model_loader import EngineUnavailable, asr_slot, translation_slot
from app.core.config import get_settings
from app.core.enums import Role
from app.core.permissions import require_roles

router = APIRouter(prefix="/ai", tags=["ai"])


class ModelStatusOut(BaseModel):
    name: str
    model_id: str
    state: str
    device: str | None
    detail: str | None
    loaded_at: datetime | None
    load_seconds: float | None


class AiStatusOut(BaseModel):
    ai_enabled: bool
    ffmpeg_available: bool
    audio_retention: bool
    models: list[ModelStatusOut]


@router.get("/status", response_model=AiStatusOut,
            dependencies=[Depends(require_roles(Role.STAFF, Role.ADMIN))])
def ai_status(load: bool = False) -> AiStatusOut:
    """Model states. `?load=true` tries to load any model not yet loaded (may take seconds)."""
    if load:
        for slot in (asr_slot, translation_slot):
            try:
                slot.get()
            except EngineUnavailable:
                pass
    s = get_settings()
    return AiStatusOut(
        ai_enabled=s.ai_enabled, ffmpeg_available=audio.ffmpeg_available(s),
        audio_retention=s.audio_keep_after_processing,
        models=[ModelStatusOut(**vars(slot.status())) for slot in (asr_slot, translation_slot)],
    )
