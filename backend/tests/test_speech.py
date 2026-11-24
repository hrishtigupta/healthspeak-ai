"""Audio upload, local transcription, translation and their failure paths.

Fake engines stand in for the models so these tests run anywhere. One opt-in
test runs the real Whisper model on a synthetic (text-to-speech) recording:
    set HEALTHSPEAK_AI_TESTS=1   (PowerShell: $env:HEALTHSPEAK_AI_TESTS="1")
"""

import io
import math
import os
import struct
import uuid
import wave
from pathlib import Path

import pytest
from sqlalchemy import select

from app.ai.model_loader import asr_slot, translation_slot
from app.ai.speech_to_text import TranscriptResult
from app.ai.translation import TranslationResult, split_sentences
from app.core.config import get_settings
from app.core.consent import CONSENT_VERSION
from app.core.enums import Role
from app.database.models import AudioTranscription, IntakeRecord

np = pytest.importorskip("numpy", reason="audio decoding needs the AI packages (numpy)")

FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_en_tts.webm"
CONSENT = {"version": CONSENT_VERSION, "granted": True, "language": "hi"}


def tone_wav(seconds=1.5, amplitude=0.3, freq=440.0) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        frames = b"".join(
            struct.pack("<h", int(amplitude * 32767 * math.sin(2 * math.pi * freq * i / 16000)))
            for i in range(int(seconds * 16000)))
        w.writeframes(frames)
    return buf.getvalue()


class FakeASR:
    device = "cpu"

    def __init__(self, text="I have a headache since this morning."):
        self.text, self.calls = text, []

    def transcribe(self, samples, language):
        self.calls.append((language, len(samples)))
        return TranscriptResult(text=self.text, language=language, model_id="fake/asr",
                                model_revision="0" * 40, device="cpu", processing_ms=5)


class FakeTranslator:
    device = "cpu"

    def translate(self, text, language):
        return TranslationResult(text=f"[EN] {text}", model_id="fake/mt", model_revision="1" * 40,
                                 device="cpu", processing_ms=3)


class Broken:
    device = "cpu"

    def transcribe(self, *a):
        raise RuntimeError("boom")

    def translate(self, *a):
        raise RuntimeError("boom")


@pytest.fixture
def patient(client):
    r = client.post("/api/patients/register", json={
        "full_name": "Synthetic Voice Patient", "phone": "9822200000", "date_of_birth": "1979-03-03",
        "gender": "female", "password": "Voice-Synthetic-1", "consent": CONSENT,
    })
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    cid = client.post("/api/conversations", headers=h).json()["id"]
    return h, cid


def upload(client, h, cid, data, ctype="audio/wav", language="en"):
    return client.post(f"/api/conversations/{cid}/transcriptions", headers=h,
                       files={"audio": ("rec", data, ctype)}, data={"language": language})


def audio_files():
    d = Path(get_settings().audio_storage_dir)
    return list(d.glob("*")) if d.exists() else []


# ---------- transcription ----------

def test_transcription_returns_text_and_deletes_audio(client, patient, db):
    h, cid = patient
    fake = FakeASR()
    asr_slot.override(fake)
    r = upload(client, h, cid, tone_wav(), language="hi")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["text"] == fake.text and body["status"] == "completed"
    assert body["language"] == "hi" and body["duration_seconds"] == pytest.approx(1.5, abs=0.05)
    assert fake.calls[0][0] == "hi"
    rec = db.get(AudioTranscription, uuid.UUID(body["id"]))
    assert rec.audio_deleted_at is not None and rec.audio_path is None
    assert len(rec.audio_sha256) == 64
    assert audio_files() == []  # raw audio not kept by default


def test_audio_kept_only_when_retention_enabled(client, patient, db, monkeypatch):
    monkeypatch.setattr(get_settings(), "audio_keep_after_processing", True)
    h, cid = patient
    asr_slot.override(FakeASR())
    body = upload(client, h, cid, tone_wav()).json()
    rec = db.get(AudioTranscription, uuid.UUID(body["id"]))
    assert rec.audio_path and Path(rec.audio_path).exists()


def test_patient_approved_text_and_raw_transcript_both_kept(client, patient, db):
    h, cid = patient
    asr_slot.override(FakeASR("i have a hedache"))
    tid = upload(client, h, cid, tone_wav()).json()["id"]
    r = client.post(f"/api/conversations/{cid}/messages", headers=h, json={
        "content": "I have a headache.", "language": "en", "input_mode": "voice_server",
        "transcription_id": tid})
    assert r.status_code == 201, r.text
    msg = r.json()["patient_message"]
    assert msg["input_mode"] == "voice_server" and msg["content"] == "I have a headache."
    rec = db.get(AudioTranscription, uuid.UUID(tid))
    assert rec.transcript_text == "i have a hedache" and str(rec.message_id) == msg["id"]
    # A transcription can only back one message.
    again = client.post(f"/api/conversations/{cid}/messages", headers=h, json={
        "content": "dup", "input_mode": "voice_server", "transcription_id": tid})
    assert again.status_code == 422


def test_voice_server_message_needs_valid_transcription(client, patient):
    h, cid = patient
    no_id = client.post(f"/api/conversations/{cid}/messages", headers=h,
                        json={"content": "x", "input_mode": "voice_server"})
    assert no_id.status_code == 422
    unknown = client.post(f"/api/conversations/{cid}/messages", headers=h, json={
        "content": "x", "input_mode": "voice_server", "transcription_id": str(uuid.uuid4())})
    assert unknown.status_code == 422
    text_with_id = client.post(f"/api/conversations/{cid}/messages", headers=h, json={
        "content": "x", "input_mode": "text", "transcription_id": str(uuid.uuid4())})
    assert text_with_id.status_code == 422


@pytest.mark.parametrize("data,ctype,status", [
    (b"not audio at all" * 10, "audio/wav", 415),          # wrong content
    (tone_wav(), "application/pdf", 415),                   # wrong type
    (b"RIFF" + b"\0" * 4 + b"WAVE" + b"\0" * 100, "audio/wav", 422),  # header only, unreadable
    (b"", "audio/wav", 422),                                # empty
], ids=["not-audio", "wrong-type", "header-only", "empty"])
def test_invalid_uploads_rejected(client, patient, data, ctype, status):
    h, cid = patient
    asr_slot.override(FakeASR())
    assert upload(client, h, cid, data, ctype).status_code == status


def test_too_large_upload_rejected(client, patient, monkeypatch):
    monkeypatch.setattr(get_settings(), "audio_max_bytes", 1000)
    h, cid = patient
    asr_slot.override(FakeASR())
    assert upload(client, h, cid, tone_wav()).status_code == 413


def test_too_long_short_and_silent_rejected(client, patient, monkeypatch, db):
    h, cid = patient
    asr_slot.override(FakeASR())
    monkeypatch.setattr(get_settings(), "audio_max_seconds", 1)
    r = upload(client, h, cid, tone_wav(seconds=2))
    assert r.status_code == 422 and "at most 1 seconds" in r.json()["detail"]
    monkeypatch.setattr(get_settings(), "audio_max_seconds", 120)
    assert upload(client, h, cid, tone_wav(seconds=0.2)).status_code == 422
    assert upload(client, h, cid, tone_wav(amplitude=0.0)).status_code == 422
    # Failures are recorded (for monitoring) and their audio is still deleted.
    codes = sorted(db.scalars(select(AudioTranscription.error_code)).all())
    assert codes == ["silent", "too_long", "too_short"]
    assert audio_files() == []


def test_model_unavailable_gives_clear_503_and_is_recorded(client, patient, db):
    h, cid = patient  # default test setup: models "not installed"
    r = upload(client, h, cid, tone_wav())
    assert r.status_code == 503 and "type your concern" in r.json()["detail"]
    rec = db.scalar(select(AudioTranscription))
    assert rec.status == "failed" and rec.error_code == "asr_unavailable"
    assert audio_files() == []


def test_model_crash_gives_503_without_internal_details(client, patient):
    h, cid = patient
    asr_slot.override(Broken())
    r = upload(client, h, cid, tone_wav())
    assert r.status_code == 503 and "boom" not in r.text


def test_empty_transcript_is_rejected(client, patient):
    h, cid = patient
    asr_slot.override(FakeASR(""))
    assert upload(client, h, cid, tone_wav()).status_code == 422


def test_other_patient_cannot_upload_to_conversation(client, patient):
    _, cid = patient
    other = client.post("/api/patients/register", json={
        "full_name": "Other Synthetic", "phone": "9822200001", "date_of_birth": "1990-01-01",
        "gender": "male", "password": "Voice-Synthetic-2", "consent": CONSENT}).json()["access_token"]
    asr_slot.override(FakeASR())
    r = upload(client, {"Authorization": f"Bearer {other}"}, cid, tone_wav())
    assert r.status_code == 404


def test_staff_cannot_upload(client, patient, auth_headers):
    _, cid = patient
    assert upload(client, auth_headers(Role.STAFF), cid, tone_wav()).status_code == 403


# ---------- translation ----------

def _submit_hindi(client, h, cid):
    client.post(f"/api/conversations/{cid}/messages", headers=h,
                json={"content": "मुझे बुखार है। सिर में दर्द है।", "language": "hi"})
    client.post(f"/api/conversations/{cid}/messages", headers=h,
                json={"content": "Since yesterday.", "language": "en"})
    return client.post(f"/api/conversations/{cid}/submit", headers=h).json()["id"]


def test_submit_translates_hindi_and_keeps_original(client, patient, db):
    h, cid = patient
    translation_slot.override(FakeTranslator())
    iid = _submit_hindi(client, h, cid)
    rec = db.get(IntakeRecord, uuid.UUID(iid))
    assert rec.translation_status == "completed"
    assert rec.english_text == "[EN] मुझे बुखार है। सिर में दर्द है।\nSince yesterday."
    assert rec.original_text == "मुझे बुखार है। सिर में दर्द है।\nSince yesterday."
    assert rec.translation_model.startswith("fake/mt@") and rec.translated_at


def test_translation_unavailable_keeps_intake_pending_then_staff_retry(client, patient, auth_headers, db):
    h, cid = patient
    iid = _submit_hindi(client, h, cid)  # models "not installed"
    rec = db.get(IntakeRecord, uuid.UUID(iid))
    assert rec.translation_status == "pending" and "not loaded" in rec.translation_error
    s = auth_headers(Role.STAFF)
    translation_slot.override(FakeTranslator())
    r = client.post(f"/api/intakes/{iid}/translate", headers=s)
    assert r.status_code == 200, r.text
    assert r.json()["translation_status"] == "completed"
    assert r.json()["english_text"].startswith("[EN] ")
    assert client.post(f"/api/intakes/{iid}/translate", headers=s).status_code == 409


def test_translation_crash_marks_failed_without_losing_intake(client, patient, db):
    h, cid = patient
    translation_slot.override(Broken())
    iid = _submit_hindi(client, h, cid)
    rec = db.get(IntakeRecord, uuid.UUID(iid))
    assert rec.translation_status == "failed" and rec.english_text is None
    assert rec.review_status == "pending_review"


def test_retry_translation_staff_only(client, patient, auth_headers):
    h, cid = patient
    iid = _submit_hindi(client, h, cid)
    for role in (Role.PATIENT, Role.DOCTOR, Role.ADMIN):
        assert client.post(f"/api/intakes/{iid}/translate", headers=auth_headers(role)).status_code == 403


def test_sentence_splitting_keeps_lines():
    assert split_sentences("एक। दो।\nتین۔ چار؟") == [["एक।", "दो।"], ["تین۔", "چار؟"]]


# ---------- status ----------

def test_ai_status_for_staff_and_admin_only(client, auth_headers):
    for role in (Role.STAFF, Role.ADMIN):
        r = client.get("/api/ai/status", headers=auth_headers(role))
        assert r.status_code == 200
        names = [m["name"] for m in r.json()["models"]]
        assert names == ["Speech recognition", "Translation"]
    for role in (Role.PATIENT, Role.DOCTOR):
        assert client.get("/api/ai/status", headers=auth_headers(role)).status_code == 403


def test_ai_status_reports_unavailable_reason(client, auth_headers):
    r = client.get("/api/ai/status", params={"load": True}, headers=auth_headers(Role.ADMIN)).json()
    assert {m["state"] for m in r["models"]} == {"unavailable"}
    assert all(m["detail"] for m in r["models"])


# ---------- optional: the real local model ----------

@pytest.mark.skipif(os.environ.get("HEALTHSPEAK_AI_TESTS") != "1",
                    reason="set HEALTHSPEAK_AI_TESTS=1 to run the real Whisper model (slow)")
def test_real_whisper_transcribes_synthetic_recording(client, patient, monkeypatch):
    from app.ai import model_loader

    monkeypatch.setattr(asr_slot, "_factory", model_loader._make_asr)
    h, cid = patient
    r = upload(client, h, cid, FIXTURE.read_bytes(), ctype="audio/webm", language="en")
    assert r.status_code == 201, r.text
    text = r.json()["text"].lower()
    for word in ("sore throat", "mild fever", "three days"):
        assert word in text, text
