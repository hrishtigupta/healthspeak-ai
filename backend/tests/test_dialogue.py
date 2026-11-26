"""The chat assistant: follow-up questions, context across messages, negation, urgency, department
suggestion, Hindi/Urdu, and what staff receive. All data is synthetic."""

import re

import pytest
from sqlalchemy import select

from app.ai import dialogue
from app.ai.dialogue_text import TEMPLATES
from app.core.consent import CONSENT_VERSION
from app.database.models import IntakeRecord, Message

CONSENT = {"version": CONSENT_VERSION, "granted": True, "language": "en"}


@pytest.fixture
def chat(client, departments):
    """Start a conversation for a synthetic patient. Returns say(text, lang) -> assistant message."""
    r = client.post("/api/patients/register", json={
        "full_name": "Synthetic Chat Patient", "phone": "9811200000", "date_of_birth": "1990-01-01",
        "gender": "female", "password": "Chat-Synthetic-1", "consent": CONSENT})
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    cid = client.post("/api/conversations", headers=h).json()["id"]

    def say(text, lang="en"):
        r = client.post(f"/api/conversations/{cid}/messages", headers=h,
                        json={"content": text, "language": lang})
        assert r.status_code == 201, r.text
        return r.json()["assistant_message"]

    say.client, say.headers, say.cid = client, h, cid
    return say


def test_example_conversation_asks_relevant_followups_then_predicts(chat):
    a1 = chat("My stomach has been hurting since yesterday.")
    assert a1["meta"]["stage"] == "asking" and a1["meta"]["asked"] == "abdomen"  # where is the pain?
    assert "since yesterday" not in a1["content"]  # duration already given: not asked again
    assert [s["term"] for s in a1["meta"]["symptoms"]] == ["stomach pain"]

    a2 = chat("Mostly in the lower abdomen, on the right side.")
    assert a2["meta"]["asked"] == "severity"  # next missing detail, not the same question again
    assert a2["meta"]["details"]["location"]["region"] == "lower"
    assert a2["meta"]["details"]["location"]["side"] == "right"

    a3 = chat("It is quite severe, and I also have a fever.")
    assert {s["term"] for s in a3["meta"]["symptoms"]} == {"stomach pain", "fever"}
    # The context from message 1 and 2 is still used: the department comes from the whole chat.
    final = a3
    for _ in range(4):
        if final["meta"]["stage"] == "ready":
            break
        final = chat("no")
    assert final["meta"]["stage"] == "ready"
    dept = final["meta"]["department"]
    assert dept["code"] == "gastroenterology" and dept["strength"] in ("clear", "likely")
    assert "stomach pain" in dept["why"]
    assert final["meta"]["caution"] is True  # lower-right pain with fever
    assert "urgent" in final["content"].lower()
    assert re.search(r"cannot diagnose or prescribe", final["content"])  # provisional + disclaimer
    questions = [m for m in chat.client.get(f"/api/conversations/{chat.cid}", headers=chat.headers)
                 .json()["messages"] if m["sender"] == "assistant" and m["meta"]["asked"]]
    slots = [m["meta"]["asked"] for m in questions]
    assert len(slots) == len(set(slots))  # never the same question twice


def test_short_message_gets_a_question_not_a_generic_reply(chat):
    a = chat("I have a cough")
    assert a["meta"]["asked"] in ("duration", "severity", "associated")
    assert "Thank you. Your message has been added" not in a["content"]
    assert a["meta"]["department"]["code"] == "pulmonology"


def test_negated_symptom_is_not_counted(chat):
    a = chat("I have a headache but I do not have fever")
    terms = [s["term"] for s in a["meta"]["symptoms"]]
    assert terms == ["headache"] and "fever" in a["meta"]["denied"]
    assert a["meta"]["department"]["code"] == "neurology"


def test_prediction_updates_when_new_symptoms_arrive(chat):
    first = chat("I have a mild headache for 2 days")
    assert first["meta"]["department"]["code"] == "neurology"
    second = chat("I also have chest pain")
    assert second["meta"]["urgent"] is True
    assert second["meta"]["department"]["code"] in ("cardiology", "neurology")
    assert second["meta"]["department"]["code"] == "cardiology"  # chest pain outweighs headache


def test_urgent_symptoms_skip_questions_and_give_emergency_guidance(chat):
    a = chat("I have severe chest pain and I cannot breathe")
    assert a["meta"]["stage"] == "urgent" and a["meta"]["asked"] is None
    assert "112" in a["content"] and "?" not in a["content"]  # no question delays emergency care
    # Chest pain and breathing trouble score equally: an honest "ambiguous, staff choose" is correct.
    dept = a["meta"]["department"]
    assert dept["status"] == "ambiguous" or dept["code"] in ("cardiology", "pulmonology")
    assert {c["name"] for c in dept["alternatives"]} >= {"Cardiology", "Pulmonology"}


def test_no_symptom_message_asks_what_is_wrong_then_stops_nagging(chat):
    a = chat("hello")
    assert a["meta"]["asked"] == "describe"
    b = chat("I feel strange")
    assert b["meta"]["asked"] == "describe_retry"
    c = chat("not sure how to say")
    assert c["meta"]["stage"] == "ready" and c["meta"]["department"] is None or c["meta"]["stage"] == "ready"


def test_hindi_conversation_is_in_hindi_and_keeps_original(chat, db):
    a = chat("मुझे कल से बुखार और पेट दर्द है", "hi")
    assert a["language"] == "hi"
    assert any("ऀ" <= ch <= "ॿ" for ch in a["content"])  # replies in Devanagari
    assert {s["term"] for s in a["meta"]["symptoms"]} == {"fever", "stomach pain"}
    mine = db.scalars(select(Message).where(Message.sender == "patient")).one()
    assert mine.content == "मुझे कल से बुखार और पेट दर्द है"  # original untouched
    assert mine.english_text is None  # no real translation was made (model not installed in tests)


def test_urdu_conversation_replies_in_urdu_and_understands_negation(chat):
    a = chat("مجھے سر درد ہے لیکن بخار نہیں ہے", "ur")
    assert any("؀" <= ch <= "ۿ" for ch in a["content"])
    assert [s["term"] for s in a["meta"]["symptoms"]] == ["headache"]
    assert "fever" in a["meta"]["denied"]
    assert a["meta"]["department"]["code"] == "neurology"


def test_selected_language_is_never_a_symptom(chat):
    for lang in ("hi", "ur"):
        a = chat("hello", lang)
        assert a["meta"]["symptoms"] == []


def test_conversation_is_persisted_in_order_and_resumable(chat):
    chat("I have a sore throat")
    chat("for three days")
    conv = chat.client.get(f"/api/conversations/{chat.cid}", headers=chat.headers).json()
    assert [m["seq"] for m in conv["messages"]] == [1, 2, 3, 4]
    assert [m["sender"] for m in conv["messages"]] == ["patient", "assistant", "patient", "assistant"]
    again = chat.client.post("/api/conversations", headers=chat.headers)
    assert again.status_code == 200 and len(again.json()["messages"]) == 4  # nothing lost


def test_staff_receive_original_messages_symptoms_and_department(chat, auth_headers):
    from app.core.enums import Role

    chat("I have a rash and itching")
    chat("since last week")
    r = chat.client.post(f"/api/conversations/{chat.cid}/submit", headers=chat.headers)
    assert r.status_code == 201
    staff = auth_headers(Role.STAFF)
    detail = chat.client.get(f"/api/intakes/{r.json()['id']}", headers=staff).json()
    assert detail["original_text"] == "I have a rash and itching\nsince last week"
    assert {s["term"] for s in detail["symptoms"]} >= {"rash", "itching"}
    assert detail["analysis"]["suggestion"]["department_code"] == "dermatology"
    assert [m["content"] for m in detail["messages"] if m["sender"] == "patient"] == [
        "I have a rash and itching", "since last week"]


def test_every_template_has_every_key_in_all_languages():
    assert set(TEMPLATES["en"]) == set(TEMPLATES["hi"]) == set(TEMPLATES["ur"])


def test_native_gloss_negation_and_duration():
    gloss, hits = dialogue.native_gloss("मुझे दो दिन से बुखार है, खांसी नहीं है", "hi")
    assert [(h.term, h.negated) for h in hits] == [("fever", False), ("cough", True)]
    assert "for 2 days" in gloss and "I do not have cough" in gloss


def test_failed_analysis_never_loses_the_patient_message(chat, monkeypatch, db):
    from app.services import dialogue_service

    def boom(*a, **k):
        raise RuntimeError("analysis broke")

    monkeypatch.setattr(dialogue_service, "reply_to", boom)
    a = chat("I have a fever")
    assert a["meta"]["stage"] == "fallback"
    assert db.scalars(select(Message).where(Message.sender == "patient")).one().content == "I have a fever"
    assert db.scalars(select(IntakeRecord)).first() is None
