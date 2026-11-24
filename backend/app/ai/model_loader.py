"""Lazy, thread-safe model loading with a clear status for each model.

States: not_loaded -> loading -> ready
                              -> unavailable (missing packages/files, AI disabled)
                              -> error       (loading crashed)
A failed load is retried at most once per RETRY_SECONDS so a broken model does
not make every request slow.
"""

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)

RETRY_SECONDS = 60


class EngineUnavailable(Exception):
    """The model cannot be used right now. The message is safe to show to staff."""


class EngineState(StrEnum):
    NOT_LOADED = "not_loaded"
    LOADING = "loading"
    READY = "ready"
    UNAVAILABLE = "unavailable"
    ERROR = "error"


@dataclass
class SlotStatus:
    name: str
    model_id: str
    state: EngineState
    device: str | None
    detail: str | None
    loaded_at: datetime | None
    load_seconds: float | None


class ModelSlot:
    def __init__(self, name: str, model_id: Callable[[], str], factory: Callable[[], Any]):
        self.name = name
        self._model_id = model_id
        self._factory = factory
        self._lock = threading.Lock()
        self._engine: Any = None
        self._state = EngineState.NOT_LOADED
        self._detail: str | None = None
        self._last_attempt = 0.0
        self._loaded_at: datetime | None = None
        self._load_seconds: float | None = None

    def get(self) -> Any:
        if self._engine is not None:
            return self._engine
        with self._lock:
            if self._engine is not None:
                return self._engine
            failed = self._state in (EngineState.UNAVAILABLE, EngineState.ERROR)
            if failed and time.monotonic() - self._last_attempt < RETRY_SECONDS:
                raise EngineUnavailable(self._detail or f"{self.name} is unavailable")
            self._state = EngineState.LOADING
            self._last_attempt = time.monotonic()
            started = time.perf_counter()
            try:
                engine = self._factory()
            except EngineUnavailable as exc:
                self._state, self._detail = EngineState.UNAVAILABLE, str(exc)
                logger.warning("%s unavailable: %s", self.name, exc)
                raise
            except Exception as exc:  # noqa: BLE001 - any crash becomes a visible error state
                self._state = EngineState.ERROR
                self._detail = f"{self.name} failed to load ({type(exc).__name__})"
                logger.exception("%s failed to load", self.name)
                raise EngineUnavailable(self._detail) from None
            self._engine = engine
            self._state, self._detail = EngineState.READY, None
            self._loaded_at = datetime.now(UTC)
            self._load_seconds = round(time.perf_counter() - started, 2)
            logger.info("%s loaded in %.1fs", self.name, self._load_seconds)
            return engine

    def status(self) -> SlotStatus:
        return SlotStatus(
            name=self.name, model_id=self._model_id(), state=self._state,
            device=getattr(self._engine, "device", None), detail=self._detail,
            loaded_at=self._loaded_at, load_seconds=self._load_seconds,
        )

    # --- used by tests ---
    def override(self, engine: Any) -> None:
        with self._lock:
            self._engine = engine
            self._state = EngineState.READY if engine is not None else EngineState.NOT_LOADED
            self._detail = None

    def reset(self) -> None:
        with self._lock:
            self._engine, self._state, self._detail = None, EngineState.NOT_LOADED, None
            self._last_attempt = 0.0


def resolve_device(setting: str) -> str:
    if setting in ("cpu", "cuda"):
        return setting
    try:
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


def _settings():
    from app.core.config import get_settings

    return get_settings()


def _make_asr():
    from app.ai.speech_to_text import WhisperEngine

    return WhisperEngine(_settings())


def _make_translator():
    from app.ai.translation import IndicTransEngine

    return IndicTransEngine(_settings())


asr_slot = ModelSlot("Speech recognition", lambda: _settings().asr_model_id, _make_asr)
translation_slot = ModelSlot("Translation", lambda: _settings().translation_model_id, _make_translator)


def missing_packages_message() -> str:
    return ("Local AI packages are not installed. Install backend/requirements-ai.txt "
            "(see backend/README.md).")


def missing_model_message(model_id: str) -> str:
    return (f"Model files for {model_id} are not on this computer. "
            "Run: python -m app.ai.download_models (see backend/README.md).")
