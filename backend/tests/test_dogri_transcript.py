"""Dogri transcript spelling suggestion: conservative, labelled, editable, and never replaces the raw
transcript. This is a display aid, NOT speech recognition. Synthetic data only."""

import io
import uuid
import wave

import pytest
from sqlalchemy import select

from app.ai.dogri_normalize import suggest
from app.ai.model_loader import asr_slot
from app.ai.speech_to_text import ASR_LIMITATION, TranscriptResult
from app.core.consent import CONSENT_VERSION
from app.core.enums import ContentLanguage
from app.database.models import AudioTranscription, Message

np = pytest.importorskip("numpy", reason="audio decoding needs the AI packages (numpy)")
CONSENT = {"version": CONSENT_VERSION, "granted": True, "language": "doi"}

# What Whisper's Hindi setting would plausibly write for Dogri speech (synthetic test text).
RAW = "मुझे कल से पेट में दर्द हो रहा है और बुखार नहीं है"


# ---------------------------------------------------------------- the rules

@pytest.mark.parametrize("hindi,dogri", [
    ("पेट में दर्द", "पेट च दर्द"),
    ("बुखार है", "बुखार ऐ"),
    ("बुखार नहीं है", "बुखार नेईं ऐ"),
    ("मुझे बुखार", "मिगी बुखार"),
    ("कल से बुखार", "कल्ल थमां बुखार"),
    ("तीन दिन से बुखार", "त्रै दिनें थमां बुखार"),
    ("मुझे उल्टी आ रही है", "मिगी उल्टी आवा करदी ऐ"),
    ("सांस लेने में तकलीफ", "सांस लैने च तकलीफ"),
    ("दाईं तरफ दर्द", "सज्जे पासे दर्द"),
    ("बुखार और खांसी", "बुखार ते खांसी"),
])
def test_known_function_words_are_respelled(hindi, dogri):
    assert suggest(hindi).text == dogri


@pytest.mark.parametrize("text", [
    "मैं डॉक्टर से मिला और दवा ली",      # "से" meaning "with", "और" meaning "and" between verbs
    "में बीमार",  # sentence-initial "में" may be the spelling of "मैं" (I)
    "I have a fever",                     # Latin text is never touched
    "दवा ली",                              # nothing to respell
    "",
])
def test_unsafe_or_unknown_text_is_left_unchanged(text):
    s = suggest(text)
    assert s.text == text and not s.changed and s.changes == []


def test_context_decides_with_and_from():
    assert suggest("डॉक्टर से बात की").text == "डॉक्टर से बात की"          # "from/with" kept
    assert suggest("सुबह से बुखार").text == "सुबह थमां बुखार"               # after a time word -> since
    assert suggest("पेट में दर्द").text == "पेट च दर्द"
    assert suggest("में खांसी").text == "में खांसी"                         # sentence-initial: left alone


def test_suggestion_reports_every_change_and_preserves_punctuation():
    s = suggest("मुझे बुखार है, सिर में दर्द है।")
    assert s.text == "मिगी बुखार ऐ, सिर च दर्द ऐ।"
    assert {(c["from"], c["to"]) for c in s.changes} >= {("मुझे", "मिगी"), ("है", "ऐ"), ("में", "च")}
    assert all(set(c) == {"from", "to", "rule"} for c in s.changes)


def test_suggestion_is_idempotent():
    once = suggest(RAW).text
    assert suggest(once).text == once


def test_the_example_transcript():
    assert suggest(RAW).text == "मिगी कल्ल थमां पेट च दर्द होआ करदा ऐ और बुखार नेईं ऐ"


# ---------------------------------------------------------------- through the API

class FakeASR:
    device = "cpu"

    def __init__(self, text=RAW):
        self.text = text

    def transcribe(self, samples, language):
        return TranscriptResult(text=self.text, language=language, model_id="fake/asr",
                                model_revision="0" * 40, device="cpu", processing_ms=1)


def wav(seconds=1.5):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(16000)
        w.writeframes(b"\x10\x10" * int(16000 * seconds))
    return buf.getvalue()


@pytest.fixture
def patient(client, departments):
    r = client.post("/api/patients/register", json={
        "full_name": "Synthetic Transcript Patient", "phone": "9866600000", "date_of_birth": "1987-07-07",
        "gender": "female", "password": "Transcript-Synthetic-1", "consent": CONSENT})
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    return client, h, client.post("/api/conversations", headers=h).json()["id"]


def upload(client, h, cid, lang):
    return client.post(f"/api/conversations/{cid}/transcriptions", headers=h,
                       files={"audio": ("rec", wav(), "audio/wav")}, data={"language": lang})


def test_api_returns_raw_text_unchanged_next_to_a_labelled_suggestion(patient, db):
    client, h, cid = patient
    asr_slot.override(FakeASR())
    body = upload(client, h, cid, "doi").json()
    assert body["text"] == RAW                                   # raw Whisper output, untouched
    assert body["suggested_text"] == "मिगी कल्ल थमां पेट च दर्द होआ करदा ऐ और बुखार नेईं ऐ"
    assert body["suggestion_changes"] and body["suggested_text"] != body["text"]
    assert "not one of the languages" in body["limitation"]       # accuracy warning is kept
    rec = db.get(AudioTranscription, uuid.UUID(body["id"]))
    assert rec.transcript_text == RAW                            # the stored record is the raw transcript
    assert ContentLanguage.DOI in ASR_LIMITATION


def test_other_languages_get_no_suggestion(patient):
    client, h, cid = patient
    asr_slot.override(FakeASR())
    for lang in ("hi", "ur", "en"):
        body = upload(client, h, cid, lang).json()
        assert body["suggested_text"] is None and body["suggestion_changes"] == []
        assert body["text"] == RAW  # Hindi/Urdu/English transcripts are exactly as before


def test_no_suggestion_when_nothing_can_be_safely_changed(patient):
    client, h, cid = patient
    asr_slot.override(FakeASR("दवा ली"))
    body = upload(client, h, cid, "doi").json()
    assert body["suggested_text"] is None and body["text"] == "दवा ली"


def test_patient_edit_is_what_the_intake_uses_and_the_raw_transcript_is_kept(patient, db):
    client, h, cid = patient
    asr_slot.override(FakeASR("मुझे बुखार है"))
    t = upload(client, h, cid, "doi").json()
    assert t["suggested_text"] == "मिगी बुखार ऐ"
    corrected = "मिगी बुखार ते खांसी ऐ"               # the patient fixes the suggestion by hand
    r = client.post(f"/api/conversations/{cid}/messages", headers=h, json={
        "content": corrected, "language": "doi", "input_mode": "voice_server", "transcription_id": t["id"]})
    assert r.status_code == 201, r.text
    mine = db.scalars(select(Message).where(Message.sender == "patient")).one()
    assert mine.content == corrected                        # corrected text, not the raw or the suggestion
    assert {s["term"] for s in r.json()["assistant_message"]["meta"]["symptoms"]} == {"fever", "cough"}
    assert db.get(AudioTranscription, uuid.UUID(t["id"])).transcript_text == "मुझे बुखार है"  # raw intact
    intake = client.post(f"/api/conversations/{cid}/submit", headers=h).json()
    assert intake["id"]


def test_accepting_the_suggestion_as_is_also_works_and_keeps_the_original(patient, db):
    client, h, cid = patient
    asr_slot.override(FakeASR("मुझे सिर में दर्द है"))
    t = upload(client, h, cid, "doi").json()
    r = client.post(f"/api/conversations/{cid}/messages", headers=h, json={
        "content": t["suggested_text"], "language": "doi", "input_mode": "voice_server",
        "transcription_id": t["id"]})
    assert r.status_code == 201
    assert {s["term"] for s in r.json()["assistant_message"]["meta"]["symptoms"]} == {"headache"}
    assert db.get(AudioTranscription, uuid.UUID(t["id"])).transcript_text == "मुझे सिर में दर्द है"
