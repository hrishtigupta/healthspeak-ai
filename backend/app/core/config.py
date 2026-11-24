"""Application settings, read from environment variables or the repo-root .env file."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# config.py -> core -> app -> backend -> repository root
REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",  # .env also holds POSTGRES_* values used only by Docker
    )

    app_name: str = "HealthSpeak AI API"
    app_version: str = "0.1.0"
    app_env: str = "development"

    # Use 127.0.0.1, not "localhost": on Windows "localhost" tries IPv6 (::1) first,
    # Docker only publishes the port on IPv4, and the IPv6 attempt can hang.
    database_url: str = (
        "postgresql+psycopg://healthspeak:change-me-local-dev-password"
        "@127.0.0.1:5432/healthspeak"
    )
    # Seconds to wait when opening a database connection before failing.
    db_connect_timeout: int = 5

    # Comma-separated, e.g. "http://localhost:5173,http://127.0.0.1:5173"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # --- Authentication ---
    session_ttl_minutes: int = 480  # 8 hours, roughly one hospital shift
    login_max_failed_attempts: int = 5
    login_lockout_minutes: int = 15
    # Country code added to bare 10-digit phone numbers ("9876543210" -> "+919876543210").
    default_phone_country_code: str = "91"

    # Password for the synthetic demo users created by `python -m app.seed`.
    seed_demo_password: str | None = None

    # Hospital's local time zone: queue days and doctor schedules use local wall-clock
    # time; everything is STORED in UTC.
    hospital_timezone: str = "Asia/Kolkata"

    # Database used by pytest. Defaults to DATABASE_URL with the name "<db>_test".
    test_database_url: str | None = None

    # --- Local AI: speech recognition + translation (Phase 5) ---
    ai_enabled: bool = True
    # Revisions are pinned so the code/weights used never change silently.
    asr_model_id: str = "openai/whisper-small"
    asr_model_revision: str = "973afd24965f72e36ca33b3055d56a652f456b4d"
    translation_model_id: str = "ai4bharat/indictrans2-indic-en-dist-200M"
    translation_model_revision: str = "d66a2122ad6d28184f3dc3797b652bd80ae3f65f"
    ai_device: str = "auto"  # auto | cpu | cuda
    # The API server never downloads models by itself; use `python -m app.ai.download_models`.
    ai_allow_download: bool = False
    ffmpeg_path: str = "ffmpeg"

    # Uploaded audio. Default folder is OUTSIDE the project (and outside OneDrive):
    # %LOCALAPPDATA%\HealthSpeakAI\audio on Windows, ~/.local/share/healthspeak-ai/audio elsewhere.
    audio_storage_dir: str | None = None
    audio_max_bytes: int = 10 * 1024 * 1024
    audio_max_seconds: int = 120
    # Raw audio is deleted right after transcription unless this is true.
    audio_keep_after_processing: bool = False

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
