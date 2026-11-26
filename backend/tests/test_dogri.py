"""Dogri (doi, Devanagari) as a patient language: validation, storage, chat, negation, urgency,
voice, translation. Synthetic data only. The Dogri sentences are illustrative test inputs written for
this project, NOT a validated clinical corpus; real Dogri wording needs review by a fluent speaker.

Opt-in (needs the local IndicTrans2 model):  set HEALTHSPEAK_AI_TESTS=1
"""

import io
import os
import uuid
import wave

import pytest
from sqlalchemy import select

from app.ai import dialogue
from app.ai.dialogue_text import (
    DEPARTMENT_NAMES,
    DOGRI_GLOSSARY,
    NATIVE_GLOSSARY,
    SYMPTOM_NAMES,
    TEMPLATES,
)
from app.ai.model_loader import asr_slot, translation_slot
from app.ai.speech_to_text import ASR_LIMITATION, WHISPER_LANGUAGE, TranscriptResult
from app.ai.translation import INDIC_CODES, TranslationResult
from app.core.consent import CONSENT_VERSION
from app.core.enums import ContentLanguage, Role, UiLanguage
from app.database.models import AudioTranscription, IntakeRecord, Message

CONSENT = {"version": CONSENT_VERSION, "granted": True, "language": "doi"}
DEVANAGARI = lambda s: any("ऀ" <= ch <= "ॿ" for ch in s)  # noqa: E731


def _register(client, phone="9833300000", **extra):
    return client.post("/api/patients/register", json={
        "full_name": "Synthetic Dogri Patient", "phone": phone, "date_of_birth": "1985-05-05",
        "gender": "female", "password": "Dogri-Synthetic-1", "consent": CONSENT, **extra})


@pytest.fixture
def chat(client, departments):
    r = _register(client)
    assert r.status_code == 201, r.text
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    cid = client.post("/api/conversations", headers=h).json()["id"]

    def say(text, lang="doi"):
        r = client.post(f"/api/conversations/{cid}/messages", headers=h,
                        json={"content": text, "language": lang})
        assert r.status_code == 201, r.text
        return r.json()["assistant_message"]

    say.client, say.headers, say.cid = client, h, cid
    return say


# ---------------------------------------------------------------- language plumbing

def test_dogri_is_in_every_language_list():
    assert UiLanguage("doi") and ContentLanguage("doi")
    assert INDIC_CODES[ContentLanguage.DOI] == "doi_Deva"
    assert set(TEMPLATES["doi"]) == set(TEMPLATES["en"])  # no wording missing
    assert set(SYMPTOM_NAMES["doi"]) == set(SYMPTOM_NAMES["hi"])
    assert set(DEPARTMENT_NAMES["doi"]) == set(DEPARTMENT_NAMES["hi"])
    assert set(DOGRI_GLOSSARY) <= set(NATIVE_GLOSSARY)  # Dogri phrases attach to known concepts


def test_registration_stores_dogri_and_returns_it(client, db):
    r = _register(client, preferred_language="doi", ui_language="doi")
    assert r.status_code == 201, r.text
    assert r.json()["patient"]["preferred_language"] == "doi"
    assert r.json()["user"]["ui_language"] == "doi"
    me = client.get("/api/patients/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"})
    assert me.json()["preferred_language"] == "doi"


def test_ui_language_preference_accepts_dogri_and_still_rejects_others(client):
    r = _register(client)
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    ok = client.patch("/api/users/me/preferences", headers=h, json={"ui_language": "doi"})
    assert ok.status_code == 200 and ok.json()["ui_language"] == "doi"
    assert client.get("/api/users/me", headers=h).json()["ui_language"] == "doi"  # persisted
    assert client.patch("/api/users/me/preferences", headers=h, json={"ui_language": "xx"}).status_code == 422
    assert client.patch("/api/users/me/preferences", headers=h, json={"ui_language": "pa"}).status_code == 422


def test_chat_api_rejects_unknown_language_but_accepts_dogri(chat):
    bad = chat.client.post(f"/api/conversations/{chat.cid}/messages", headers=chat.headers,
                           json={"content": "hello", "language": "xx"})
    assert bad.status_code == 422
    assert chat("मिगी बुखार ऐ")["language"] == "doi"


def test_consent_for_dogri_falls_back_to_reviewed_hindi_text(client):
    r = client.get("/api/consent/current", params={"language": "doi"})
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == CONSENT_VERSION and body["text"] and DEVANAGARI(body["text"])
    hindi = client.get("/api/consent/current", params={"language": "hi"}).json()
    assert body["text"] == hindi["text"]  # no unreviewed machine-written legal text


def test_kiosk_heartbeat_language_literal_includes_dogri():
    from app.routers.kiosks import Heartbeat

    assert Heartbeat(ui_language="doi").ui_language == "doi"


# ---------------------------------------------------------------- understanding Dogri

@pytest.mark.parametrize("text,term", [
    ("मिगी पेट च दर्द ऐ", "stomach pain"),
    ("मिगी सिर च दर्द ऐ", "headache"),
    ("मिगी बुखार ऐ", "fever"),
    ("मिगी खांसी ऐ", "cough"),
    ("मिगी साह लैने च परेशानी ऐ", "breathing difficulty"),
    ("मिगी उल्टी आवा करदी ऐ", "vomiting"),
    ("मेरी छाती च दर्द ऐ", "chest pain"),
    ("मेरे गोड्डे च दर्द ऐ", "knee pain"),
    ("मिगी कन्न च दर्द ऐ", "ear pain"),
])
def test_dogri_phrases_are_recognised(text, term):
    _, hits = dialogue.native_gloss(text, "doi")
    assert (term, False) in [(h.term, h.negated) for h in hits], text


def test_dogri_negation_and_present_symptoms_are_separated():
    gloss, hits = dialogue.native_gloss("मिगी सिर च दर्द ऐ पर बुखार नेईं ऐ", "doi")
    assert [(h.term, h.negated) for h in hits if h.term != "pain (location not stated)"] == [
        ("headache", False), ("fever", True)]
    assert "I do not have fever" in gloss
    # Negation before the symptom, and a clause break that stops negation leaking.
    _, hits = dialogue.native_gloss("मिगी खांसी नेईं ऐ ते बुखार ऐ", "doi")
    assert {(h.term, h.negated) for h in hits} == {("cough", True), ("fever", False)}


def test_dogri_duration_words():
    gloss, _ = dialogue.native_gloss("मिगी त्रै दिनें थमां बुखार ऐ", "doi")
    assert "for 3 days" in gloss
    gloss, _ = dialogue.native_gloss("मिगी कल्लै थमां पेट च दर्द होआ करदा ऐ।", "doi")
    assert "since yesterday" in gloss


def test_dogri_answers_to_questions_are_parsed():
    d = dialogue.parse_answer("abdomen", "", "थल्ले, सज्जे पासे", "doi")
    assert d["location"]["region"] == "lower" and d["location"]["side"] == "right"
    d = dialogue.parse_answer("severity", "", "बड़ा तेज ऐ", "doi")
    assert d["severity"] == "severe"
    assert dialogue.parse_answer("associated", "", "नेईं", "doi") == {"associated_none": True}


# ---------------------------------------------------------------- the conversation

def test_dogri_conversation_asks_in_dogri_keeps_context_and_updates_department(chat, db):
    first = "मिगी कल्लै थमां पेट च दर्द होआ करदा ऐ।"
    a1 = chat(first)
    assert a1["language"] == "doi" and DEVANAGARI(a1["content"])
    assert a1["meta"]["stage"] == "asking" and a1["meta"]["asked"] == "abdomen"
    assert [s["term"] for s in a1["meta"]["symptoms"]] == ["stomach pain"]
    assert "कुत्थें" in a1["content"]  # a Dogri question word, not Hindi "कहाँ"
    assert a1["content"] != TEMPLATES["hi"]["q_abdomen"]

    a2 = chat("थल्ले, सज्जे पासे")
    assert a2["meta"]["details"]["location"] == {"region": "lower", "side": "right",
                                                 "said": "थल्ले, सज्जे पासे"}
    assert a2["meta"]["asked"] == "severity"  # next missing detail, never the same question twice

    a3 = chat("बड़ा तेज ऐ ते मिगी बुखार बी ऐ")
    assert {s["term"] for s in a3["meta"]["symptoms"]} == {"stomach pain", "fever"}
    final = a3
    for _ in range(4):
        if final["meta"]["stage"] == "ready":
            break
        final = chat("नेईं")
    assert final["meta"]["stage"] == "ready"
    dept = final["meta"]["department"]
    assert dept["code"] == "gastroenterology" and dept["strength"] in ("clear", "likely")
    assert final["meta"]["caution"] is True  # lower-right pain with fever, from earlier messages
    assert "पेट रोग" in final["content"]  # department explained by name, in Devanagari
    assert "सिर्फ" in final["content"]  # "this is only preliminary", in Dogri

    first_msg = db.scalars(select(Message).where(Message.sender == "patient").order_by(Message.seq)).first()
    assert first_msg.content == first and first_msg.language == "doi"  # original spelling untouched


def test_new_symptom_changes_the_prediction(chat):
    a = chat("मिगी सिर च दर्द ऐ")
    assert a["meta"]["department"]["code"] == "neurology"
    b = chat("ते मिगी खांसी ऐ ते साह लैने च परेशानी बी ऐ")
    terms = {s["term"] for s in b["meta"]["symptoms"]}
    assert {"cough", "breathing difficulty", "headache"} <= terms
    assert b["meta"]["stage"] == "urgent"  # the new red-flag symptom is not ignored


def test_denied_symptom_is_not_counted_and_is_explained(chat):
    a = chat("मिगी सिर च दर्द ऐ पर बुखार नेईं ऐ")
    assert [s["term"] for s in a["meta"]["symptoms"]] == ["headache"]
    assert "fever" in a["meta"]["denied"]


@pytest.mark.parametrize("text", [
    "मेरी छाती च दर्द ऐ",
    "मिगी साह लैने च परेशानी ऐ",
    "मिगी साह लैना औखा ऐ",
    "मैं बेहोश होई गेआ",
])
def test_dogri_emergency_symptoms_get_guidance_before_any_question(chat, text):
    a = chat(text)
    assert a["meta"]["stage"] == "urgent" and a["meta"]["urgent"] is True and a["meta"]["asked"] is None
    assert "112" in a["content"] and "?" not in a["content"] and DEVANAGARI(a["content"])
    assert "जाओ" in a["content"]  # Dogri imperative: "go"


def test_negated_emergency_symptom_is_not_an_emergency(chat):
    a = chat("मिगी बुखार ऐ पर छाती च दर्द नेईं ऐ")
    assert a["meta"]["urgent"] is False
    assert "chest pain" in a["meta"]["denied"]


def test_selected_language_is_never_treated_as_a_symptom(chat):
    a = chat("नमस्ते")
    assert a["meta"]["symptoms"] == []


def test_dogri_review_and_submit_reach_staff_with_original_text(chat, auth_headers, db):
    english = {"मिगी कल्लै थमां पेट च दर्द होआ करदा ऐ।": "I have had abdominal pain since yesterday.",
               "मिगी बुखार बी ऐ": "I also have a fever."}

    class Translator:
        device = "cpu"

        def translate(self, text, language):
            assert language == ContentLanguage.DOI
            return TranslationResult(text=english[text], model_id="fake/mt", model_revision="1" * 40,
                                     device="cpu", processing_ms=1)

    translation_slot.override(Translator())
    chat("मिगी कल्लै थमां पेट च दर्द होआ करदा ऐ।")
    chat("मिगी बुखार बी ऐ")
    r = chat.client.post(f"/api/conversations/{chat.cid}/submit", headers=chat.headers)
    assert r.status_code == 201, r.text
    assert r.json()["original_language"] == "doi"
    staff = auth_headers(Role.STAFF)
    detail = chat.client.get(f"/api/intakes/{r.json()['id']}", headers=staff).json()
    assert detail["original_language"] == "doi"
    assert detail["original_text"] == "मिगी कल्लै थमां पेट च दर्द होआ करदा ऐ।\nमिगी बुखार बी ऐ"
    assert {s["term"] for s in detail["symptoms"]} >= {"stomach pain", "fever"}
    assert detail["english_text"] == "I have had abdominal pain since yesterday.\nI also have a fever."
    assert detail["analysis"]["suggestion"]["department_code"] == "gastroenterology"
    assert [m["content"] for m in detail["messages"] if m["sender"] == "patient"] == [
        "मिगी कल्लै थमां पेट च दर्द होआ करदा ऐ।", "मिगी बुखार बी ऐ"]
    # Staff can still correct the extracted text, separately from the original.
    fixed = chat.client.patch(f"/api/intakes/{r.json()['id']}", headers=staff,
                              json={"final_text": "Abdominal pain since yesterday, fever.", "reason": "check"})
    assert fixed.status_code == 200
    again = chat.client.get(f"/api/intakes/{r.json()['id']}", headers=staff).json()
    assert again["original_text"].startswith("मिगी कल्लै थमां")


def test_dogri_message_is_translated_with_the_dogri_model_tag_and_original_kept(chat, db):
    calls = []

    class Recorder:
        device = "cpu"

        def translate(self, text, language):
            calls.append(language)
            return TranslationResult(text="I have a fever.", model_id="fake/mt", model_revision="1" * 40,
                                     device="cpu", processing_ms=1)

    translation_slot.override(Recorder())
    a = chat("मिगी बुखार ऐ")
    assert calls and calls[0] == ContentLanguage.DOI
    mine = db.scalars(select(Message).where(Message.sender == "patient")).one()
    assert mine.content == "मिगी बुखार ऐ" and mine.english_text == "I have a fever."
    assert a["meta"]["symptoms"][0]["term"] == "fever"


# ---------------------------------------------------------------- voice

class _FakeASR:
    device = "cpu"

    def __init__(self):
        self.calls = []

    def transcribe(self, samples, language):
        self.calls.append(language)
        return TranscriptResult(text="मिगी बुखार ऐ", language=language, model_id="fake/asr",
                                model_revision="0" * 40, device="cpu", processing_ms=1)


def _wav(seconds=1.5):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(16000)
        w.writeframes(b"\x10\x10" * int(16000 * seconds))
    return buf.getvalue()


def test_dogri_voice_upload_is_accepted_and_the_limitation_is_reported(chat, db):
    pytest.importorskip("numpy")
    fake = _FakeASR()
    asr_slot.override(fake)
    r = chat.client.post(f"/api/conversations/{chat.cid}/transcriptions", headers=chat.headers,
                         files={"audio": ("rec", _wav(), "audio/wav")}, data={"language": "doi"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["language"] == "doi" and body["text"] == "मिगी बुखार ऐ"
    assert "Dogri is not one of the languages" in body["limitation"]  # never silent
    assert fake.calls == [ContentLanguage.DOI]
    assert db.get(AudioTranscription, uuid.UUID(body["id"])).language == "doi"
    # No warning for languages Whisper really supports.
    hi = chat.client.post(f"/api/conversations/{chat.cid}/transcriptions", headers=chat.headers,
                          files={"audio": ("rec", _wav(), "audio/wav")}, data={"language": "hi"})
    assert hi.json()["limitation"] is None


def test_reviewed_voice_text_is_kept_next_to_the_raw_transcript(chat, db):
    pytest.importorskip("numpy")
    asr_slot.override(_FakeASR())
    t = chat.client.post(f"/api/conversations/{chat.cid}/transcriptions", headers=chat.headers,
                         files={"audio": ("rec", _wav(), "audio/wav")}, data={"language": "doi"}).json()
    r = chat.client.post(f"/api/conversations/{chat.cid}/messages", headers=chat.headers, json={
        "content": "मिगी बुखार ते खांसी ऐ", "language": "doi", "input_mode": "voice_server",
        "transcription_id": t["id"]})
    assert r.status_code == 201, r.text
    mine = db.scalars(select(Message).where(Message.sender == "patient")).one()
    assert mine.content == "मिगी बुखार ते खांसी ऐ"  # corrected text drives the extraction
    assert {s["term"] for s in r.json()["assistant_message"]["meta"]["symptoms"]} == {"fever", "cough"}
    assert db.get(AudioTranscription, uuid.UUID(t["id"])).transcript_text == "मिगी बुखार ऐ"  # raw kept


def test_whisper_has_no_dogri_token_and_the_hindi_fallback_is_documented():
    from transformers.models.whisper.tokenization_whisper import LANGUAGES

    assert "doi" not in LANGUAGES and "dogri" not in LANGUAGES.values()  # verified, not assumed
    assert WHISPER_LANGUAGE[ContentLanguage.DOI] == "hindi"
    assert ContentLanguage.DOI in ASR_LIMITATION


# ---------------------------------------------------------------- the real translation model (opt-in)

@pytest.mark.skipif(os.environ.get("HEALTHSPEAK_AI_TESTS") != "1",
                    reason="set HEALTHSPEAK_AI_TESTS=1 to run the real IndicTrans2 model (slow)")
@pytest.mark.parametrize("dogri,expected", [
    ("मिगी कल्लै थमां पेट च दर्द होआ करदा ऐ।", ("pain", "yesterday")),
    ("मिगी बुखार ऐ ते सिर च दर्द ऐ।", ("fever", "headache")),
    ("मिगी साह लैने च परेशानी ऐ।", ("breath",)),
    ("मिगी बुखार नेईं ऐ।", ("fever", "not")),
    ("मेरी छाती च दर्द ऐ।", ("chest pain",)),
])
def test_real_indictrans2_translates_dogri(dogri, expected):
    from app.core.config import get_settings
    from app.ai.translation import IndicTransEngine

    engine = IndicTransEngine(get_settings())
    out = engine.translate(dogri, ContentLanguage.DOI).text.lower().replace("don't", "do not")
    for word in expected:
        assert word in out.replace("n't", " not"), out


# ---------------------------------------------------------------- Dogri replies across the whole flow

LATIN_WORD = __import__("re").compile(r"[A-Za-z]{2,}")


def test_every_symptom_term_has_a_dogri_display_name():
    from app.ai.lexicon import SYMPTOMS

    missing = {t for t in SYMPTOMS if t not in SYMPTOM_NAMES["doi"]}
    assert not missing, missing


def test_every_assistant_message_of_a_dogri_chat_is_in_dogri(chat):
    """Questions, clarifications, the department explanation: Devanagari only, no English words."""
    replies = [chat("मिगी कल्लै थमां पेट च दर्द होआ करदा ऐ।")]
    replies.append(chat("थल्ले, सज्जे पासे"))
    replies.append(chat("बड़ा तेज ऐ ते मिगी बुखार बी ऐ"))
    for _ in range(4):
        if replies[-1]["meta"]["stage"] == "ready":
            break
        replies.append(chat("नेईं"))
    assert replies[-1]["meta"]["stage"] == "ready"
    stages = [r["meta"]["stage"] for r in replies]
    assert "asking" in stages and stages[-1] == "ready"
    for r in replies:
        assert r["language"] == "doi" and DEVANAGARI(r["content"]), r["content"]
        assert not LATIN_WORD.findall(r["content"]), r["content"]
    asked = [r["meta"]["asked"] for r in replies if r["meta"]["asked"]]
    assert len(asked) == len(set(asked)), asked  # never the same question twice
    assert len({r["content"] for r in replies}) == len(replies)


def test_dogri_urgent_guidance_has_no_english_words_and_no_question(chat):
    a = chat("मिगी साह लैने च परेशानी ऐ ते मैं बेहोश होई गेआ")
    assert a["meta"]["stage"] == "urgent" and "?" not in a["content"]
    assert not LATIN_WORD.findall(a["content"]), a["content"]


def test_dogri_fallback_reply_is_dogri_when_analysis_breaks(chat, monkeypatch, db):
    from app.services import dialogue_service

    def boom(*a, **k):
        raise RuntimeError("analysis broke")

    monkeypatch.setattr(dialogue_service, "reply_to", boom)
    a = chat("मिगी बुखार ऐ")
    assert a["meta"]["stage"] == "fallback" and a["language"] == "doi"
    assert DEVANAGARI(a["content"]) and not LATIN_WORD.findall(a["content"]), a["content"]
    assert db.scalars(select(Message).where(Message.sender == "patient")).one().content == "मिगी बुखार ऐ"


def test_department_card_data_has_a_dogri_name_and_english_is_unchanged(chat):
    a = chat("मिगी सिर च दर्द ऐ")
    dept = a["meta"]["department"]
    assert dept["name"] == "Neurology" and DEVANAGARI(dept["name_local"])
    assert dept["name_local"] == DEPARTMENT_NAMES["doi"]["neurology"]


def test_switching_languages_mid_conversation_keeps_context_and_each_reply_follows_its_message(chat):
    a1 = chat("मेरे सिर च दर्द ऐ", "doi")
    a2 = chat("I also have a fever", "en")
    a3 = chat("मुझे खांसी भी है", "hi")
    a4 = chat("मिगी उल्टी आवा करदी ऐ", "doi")
    assert (a1["language"], a2["language"], a3["language"], a4["language"]) == ("doi", "en", "hi", "doi")
    assert DEVANAGARI(a1["content"]) and a1["content"] != a3["content"]
    assert not DEVANAGARI(a2["content"])  # English stays English
    assert DEVANAGARI(a3["content"]) and "सज्जे" not in a3["content"]  # Hindi wording, not Dogri
    assert any(w in a4["content"] for w in ("तुसेंगी", "तुंदे", "तुसें", "ऐ"))
    terms = {s["term"] for s in a4["meta"]["symptoms"]}
    assert {"headache", "fever", "cough", "vomiting"} <= terms  # all four turns remembered


def test_english_and_hindi_replies_are_unchanged_by_dogri(client, departments):
    from app.ai.dialogue import plan_turn  # noqa: F401 - import proves the module still loads

    assert TEMPLATES["en"]["q_abdomen"].startswith("Where exactly is the pain")
    assert TEMPLATES["hi"]["q_pain_location"] == "दर्द ठीक किस जगह है?"
    assert TEMPLATES["doi"]["q_pain_location"] != TEMPLATES["hi"]["q_pain_location"]


def test_duration_and_negation_survive_across_dogri_turns(chat):
    chat("मिगी त्रै दिनें थमां बुखार ऐ")
    b = chat("खांसी नेईं ऐ")
    assert "cough" in b["meta"]["denied"]
    assert [s["term"] for s in b["meta"]["symptoms"]] == ["fever"]
    assert b["meta"]["asked"] != "duration"  # "three days" was already said: not asked again
