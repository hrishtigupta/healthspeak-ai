"""Hindi/Urdu -> English translation with a local IndicTrans2 model.

Default model: ai4bharat/indictrans2-indic-en-dist-200M (distilled, ~0.9 GB).
The larger ai4bharat/indictrans2-indic-en-1B (~4.1 GB) can be selected with
TRANSLATION_MODEL_ID / TRANSLATION_MODEL_REVISION in .env.

Both models are "gated" on Hugging Face: you must log in and accept the model's
terms once before `python -m app.ai.download_models --translation` can fetch them.
The model's own Python code is executed (trust_remote_code), so the revision is
pinned in settings to a reviewed commit.
"""

import re
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

INDIC_CODES = {
    ContentLanguage.HI: "hin_Deva",
    ContentLanguage.UR: "urd_Arab",
}
TARGET = "eng_Latn"

# Split after sentence-ending punctuation: . ! ? Hindi danda (।), Urdu full stop (۔), Arabic ?
_SENTENCE_END = re.compile(r"(?<=[.!?।۔؟])\s+")


def split_sentences(text: str) -> list[list[str]]:
    """Lines -> sentences, so the line structure can be restored after translation."""
    return [[s for s in _SENTENCE_END.split(line.strip()) if s] for line in text.splitlines()]


@dataclass
class TranslationResult:
    text: str
    model_id: str
    model_revision: str
    device: str
    processing_ms: int


class IndicTransEngine:
    def __init__(self, settings: Settings):
        if not settings.ai_enabled:
            raise EngineUnavailable("Local AI is switched off (AI_ENABLED=false).")
        try:
            import torch
            from IndicTransToolkit.processor import IndicProcessor
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        except ImportError:
            raise EngineUnavailable(missing_packages_message()) from None

        self._torch = torch
        self.model_id = settings.translation_model_id
        self.revision = settings.translation_model_revision
        self.device = resolve_device(settings.ai_device)
        local_only = not settings.ai_allow_download
        try:
            self._tokenizer = AutoTokenizer.from_pretrained(
                self.model_id, revision=self.revision, trust_remote_code=True,
                local_files_only=local_only)
            self._model = AutoModelForSeq2SeqLM.from_pretrained(
                self.model_id, revision=self.revision, trust_remote_code=True,
                local_files_only=local_only,
                dtype=torch.float16 if self.device == "cuda" else torch.float32,
            ).to(self.device).eval()
        except OSError:
            raise EngineUnavailable(missing_model_message(self.model_id)) from None
        self._processor = IndicProcessor(inference=True)

    def translate(self, text: str, language: ContentLanguage) -> TranslationResult:
        if language not in INDIC_CODES:
            raise ValueError(f"No translation needed/possible for {language}")
        started = time.perf_counter()
        lines = split_sentences(text)
        flat = [s for line in lines for s in line]
        translated: list[str] = []
        for i in range(0, len(flat), 16):
            batch = self._processor.preprocess_batch(flat[i:i + 16], src_lang=INDIC_CODES[language],
                                                     tgt_lang=TARGET)
            inputs = self._tokenizer(batch, truncation=True, padding="longest", return_tensors="pt",
                                     return_attention_mask=True).to(self.device)
            with self._torch.no_grad():
                # use_cache=False: the model's bundled code breaks on transformers' newer
                # cache objects (verified with transformers 4.57). Slower, but correct.
                out = self._model.generate(**inputs, use_cache=False, min_length=0, max_length=256,
                                           num_beams=5, num_return_sequences=1)
            decoded = self._tokenizer.batch_decode(out, skip_special_tokens=True,
                                                   clean_up_tokenization_spaces=True)
            translated.extend(self._processor.postprocess_batch(decoded, lang=TARGET))
        # Rebuild the original line structure.
        it = iter(translated)
        english = "\n".join(" ".join(next(it) for _ in line) for line in lines)
        return TranslationResult(text=english, model_id=self.model_id, model_revision=self.revision,
                                 device=self.device,
                                 processing_ms=int((time.perf_counter() - started) * 1000))
