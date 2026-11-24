"""Audio upload validation, private temporary storage and decoding (via ffmpeg)."""

import hashlib
import os
import shutil
import subprocess
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path

from app.core.config import Settings

SAMPLE_RATE = 16000
MIN_SECONDS = 0.5
SILENCE_PEAK = 0.01  # below this peak amplitude we treat the clip as silent

# Content types browsers send for recordings / common audio files.
ALLOWED_CONTENT_TYPES = {
    "audio/webm", "video/webm", "audio/ogg", "audio/wav", "audio/x-wav", "audio/wave",
    "audio/vnd.wave", "audio/mpeg", "audio/mp3", "audio/mp4", "audio/x-m4a", "audio/aac",
}


class AudioRejected(Exception):
    """The upload is not acceptable. `code` is machine-readable, the message is user-facing."""

    def __init__(self, code: str, message: str, status: int = 422):
        super().__init__(message)
        self.code = code
        self.status = status


@dataclass
class StoredAudio:
    path: Path
    sha256: str
    size: int
    kind: str


def sniff_kind(data: bytes) -> str | None:
    """Identify the container from its first bytes (do not trust the file name/type)."""
    if data[:4] == b"\x1a\x45\xdf\xa3":
        return "webm"
    if data[:4] == b"OggS":
        return "ogg"
    if data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        return "wav"
    if data[4:8] == b"ftyp":
        return "mp4"
    if data[:3] == b"ID3" or (len(data) > 1 and data[0] == 0xFF and data[1] & 0xE0 == 0xE0):
        return "mp3"
    return None


def check_upload(data: bytes, content_type: str | None, settings: Settings) -> str:
    base_type = (content_type or "").split(";")[0].strip().lower()
    if base_type not in ALLOWED_CONTENT_TYPES:
        raise AudioRejected("unsupported_type", "Unsupported audio format.", 415)
    if len(data) > settings.audio_max_bytes:
        raise AudioRejected("too_large", "The recording is too large.", 413)
    if len(data) < 64:
        raise AudioRejected("empty", "The recording is empty.")
    kind = sniff_kind(data)
    if kind is None:
        raise AudioRejected("unsupported_type", "The file is not a recognised audio recording.", 415)
    return kind


def storage_dir(settings: Settings) -> Path:
    if settings.audio_storage_dir:
        base = Path(settings.audio_storage_dir)
    elif sys.platform == "win32" and os.environ.get("LOCALAPPDATA"):
        base = Path(os.environ["LOCALAPPDATA"]) / "HealthSpeakAI" / "audio"
    else:
        base = Path.home() / ".local" / "share" / "healthspeak-ai" / "audio"
    base.mkdir(parents=True, exist_ok=True)
    return base


def store(data: bytes, kind: str, settings: Settings) -> StoredAudio:
    """Write the upload under a random name in the private audio folder."""
    path = storage_dir(settings) / f"{uuid.uuid4().hex}.{kind}"
    path.write_bytes(data)
    return StoredAudio(path=path, sha256=hashlib.sha256(data).hexdigest(), size=len(data), kind=kind)


def delete(path: Path) -> bool:
    try:
        path.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def ffmpeg_available(settings: Settings) -> bool:
    return shutil.which(settings.ffmpeg_path) is not None or Path(settings.ffmpeg_path).is_file()


def decode(path: Path, settings: Settings):
    """Decode to 16 kHz mono float32 samples and check length and loudness."""
    try:
        import numpy as np
    except ImportError:
        from app.ai.model_loader import EngineUnavailable, missing_packages_message

        raise EngineUnavailable(missing_packages_message()) from None
    if not ffmpeg_available(settings):
        from app.ai.model_loader import EngineUnavailable

        raise EngineUnavailable("ffmpeg is not installed on the server.")
    max_seconds = settings.audio_max_seconds
    cmd = [settings.ffmpeg_path, "-nostdin", "-loglevel", "error", "-i", str(path),
           "-t", str(max_seconds + 1), "-f", "f32le", "-ac", "1", "-ar", str(SAMPLE_RATE), "-"]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=60, check=False)
    except subprocess.TimeoutExpired:
        raise AudioRejected("unreadable", "The recording could not be processed.") from None
    if proc.returncode != 0 or not proc.stdout:
        raise AudioRejected("unreadable", "The recording could not be read.")
    samples = np.frombuffer(proc.stdout, dtype=np.float32)
    seconds = len(samples) / SAMPLE_RATE
    if seconds > max_seconds:
        raise AudioRejected("too_long", f"Recordings can be at most {max_seconds} seconds.")
    if seconds < MIN_SECONDS:
        raise AudioRejected("too_short", "The recording is too short.")
    if float(np.max(np.abs(samples))) < SILENCE_PEAK:
        raise AudioRejected("silent", "We could not hear any speech. Please try again closer to the microphone.")
    return samples, round(seconds, 2)
