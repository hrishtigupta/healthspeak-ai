"""Speech recognition with a local Whisper model (default: openai/whisper-small)."""

import time
from dataclasses import dataclass

from app.ai.model_loader import (
    EngineUnavailable,
    missing_model_message,
    missing_packages_message,
    resolve_device,
)
from app.core.config import Settings
from app.core.enums import ContentLanguage

# Whisper's language names. Passing the patient's chosen language avoids
# mis-detection between Hindi and Urdu, which sound very similar.
WHISPER_LANGUAGE = {
    ContentLanguage.EN: "english",
    ContentLanguage.HI: "hindi",
    ContentLanguage.UR: "urdu",
    # Whisper has NO Dogri language token (checked against its tokenizer's language list). Dogri is
    # decoded with the Hindi token, the closest Devanagari language it knows, and this is never hidden:
    # see ASR_LIMITATION below, which the API returns and the app shows next to the transcript.
    ContentLanguage.DOI: "hindi",
}

ASR_LIMITATION = {
    ContentLanguage.DOI: (
        "Dogri is not one of the languages the speech model was trained for, so this transcript was "
        "produced with its Hindi setting and may contain mistakes, Hindi words in place of Dogri "
        "words, or missing words. Please read it carefully and correct it before sending."
    ),
}


@dataclass
class TranscriptResult:
    text: str
    language: ContentLanguage
    model_id: str
    model_revision: str
    device: str
    processing_ms: int


class WhisperEngine:
    def __init__(self, settings: Settings):
        if not settings.ai_enabled:
            raise EngineUnavailable("Local AI is switched off (AI_ENABLED=false).")
        try:
            import torch
            from transformers import WhisperForConditionalGeneration, WhisperProcessor, pipeline
        except ImportError:
            raise EngineUnavailable(missing_packages_message()) from None

        self.model_id = settings.asr_model_id
        self.revision = settings.asr_model_revision
        self.device = resolve_device(settings.ai_device)
        local_only = not settings.ai_allow_download
        try:
            processor = WhisperProcessor.from_pretrained(
                self.model_id, revision=self.revision, local_files_only=local_only)
            model = WhisperForConditionalGeneration.from_pretrained(
                self.model_id, revision=self.revision, local_files_only=local_only,
                dtype=torch.float16 if self.device == "cuda" else torch.float32)
        except OSError:
            raise EngineUnavailable(missing_model_message(self.model_id)) from None
        self._pipe = pipeline(
            "automatic-speech-recognition", model=model, tokenizer=processor.tokenizer,
            feature_extractor=processor.feature_extractor, device=self.device, dtype=model.dtype,
        )

    def transcribe(self, samples, language: ContentLanguage) -> TranscriptResult:
        started = time.perf_counter()
        # Longer than Whisper's 30 s window: use its own sequential long-form decoding,
        # which needs timestamp prediction switched on.
        long_form = len(samples) > 30 * 16000
        out = self._pipe(
            {"raw": samples, "sampling_rate": 16000},
            return_timestamps=long_form or None,
            generate_kwargs={"language": WHISPER_LANGUAGE[language], "task": "transcribe"},
        )
        return TranscriptResult(
            text=(out.get("text") or "").strip(), language=language, model_id=self.model_id,
            model_revision=self.revision, device=self.device,
            processing_ms=int((time.perf_counter() - started) * 1000),
        )
