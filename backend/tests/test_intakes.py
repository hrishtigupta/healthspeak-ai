"""Conversations, intake submission, staff review and access control."""

import re
import uuid

import pytest
from sqlalchemy import select

from app.core.consent import CONSENT_VERSION
from app.core.enums import Role
from app.database.models import AuditEvent, IntakeRecord, IntakeRevision

CONSENT = {"version": CONSENT_VERSION, "granted": True, "language": "en"}
HINDI = "मुझे कल से तेज़ बुखार और सिरदर्द है।"


@pytest.fixture
def patient(client):
    """A registered patient with valid consent. Returns (headers, patient_id)."""

    def _make(phone="9811100000", name="Synthetic Intake Patient"):
        r = client.post("/api/patients/register", json={
            "full_name": name, "phone": phone, "date_of_birth": "1985-06-01", "gender": "male",
            "password": "Intake-Synthetic-1", "consent": CONSENT,
        })
        assert r.status_code == 201, r.text
        return {"Authorization": f"Bearer {r.json()['access_token']}"}, r.json()["patient"]["id"]

    return _make


def _converse(client, h, *messages):
    conv = client.post("/api/conversations", headers=h)
    assert conv.status_code in (200, 201), conv.text
    cid = conv.json()["id"]
    for content, lang, mode in messages:
        r = client.post(f"/api/conversations/{cid}/messages", headers=h,
                        json={"content": content, "language": lang, "input_mode": mode})
        assert r.status_code == 201, r.text
    return cid


def _submit(client, h, *messages):
    cid = _converse(client, h, *messages)
    r = client.post(f"/api/conversations/{cid}/submit", headers=h)
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ---------- patient conversation ----------

def test_open_conversation_is_resumed_not_duplicated(client, patient):
    h, _ = patient()
    first = client.post("/api/conversations", headers=h)
    second = client.post("/api/conversations", headers=h)
    assert first.status_code == 201 and second.status_code == 200
    assert first.json()["id"] == second.json()["id"]


def test_message_stored_exactly_with_acknowledgement(client, patient):
    h, _ = patient()
    cid = client.post("/api/conversations", headers=h).json()["id"]
    text = "  I have had a cough for 3 days.\nNo fever.  "
    r = client.post(f"/api/conversations/{cid}/messages", headers=h,
                    json={"content": text, "language": "en"})
    assert r.status_code == 201
    body = r.json()
    assert body["patient_message"]["content"] == text  # not trimmed or altered
    assert body["patient_message"]["seq"] == 1 and body["assistant_message"]["seq"] == 2
    assert body["assistant_message"]["sender"] == "assistant"
    conv = client.get(f"/api/conversations/{cid}", headers=h).json()
    assert [m["sender"] for m in conv["messages"]] == ["patient", "assistant"]


def test_acknowledgement_never_contains_medical_advice(client, patient):
    h, _ = patient()
    cid = client.post("/api/conversations", headers=h).json()["id"]
    for lang in ("en", "hi", "ur"):
        ack = client.post(f"/api/conversations/{cid}/messages", headers=h,
                          json={"content": "chest pain", "language": lang}).json()["assistant_message"]
        assert ack["language"] == lang
        # The assistant may DISCLAIM diagnosing/prescribing (a fixed sentence); it must never do either.
        from app.ai.dialogue_text import TEMPLATES

        lowered = ack["content"].replace(TEMPLATES[lang]["prelim"], "").lower()
        for pattern in (r"\bdiagnos", r"\bprescri", r"\byou have\b", r"\btake\b", r"\bdose\b"):
            assert not re.search(pattern, lowered), pattern


def test_english_intake_needs_no_translation(client, patient):
    h, _ = patient()
    iid = _submit(client, h, ("Knee pain when walking.", "en", "text"),
                  ("Started last week.", "en", "voice_browser"))
    mine = client.get("/api/patients/me/intakes", headers=h).json()
    assert mine[0]["id"] == iid
    assert mine[0]["original_text"] == "Knee pain when walking.\nStarted last week."
    assert mine[0]["review_status"] == "pending_review"


def test_hindi_intake_keeps_original_and_waits_for_translation(client, patient, auth_headers, db):
    h, _ = patient()
    iid = _submit(client, h, (HINDI, "hi", "voice_browser"))
    rec = db.get(IntakeRecord, uuid.UUID(iid))
    assert rec.original_text == HINDI and rec.original_language == "hi"
    assert rec.english_text is None and rec.translation_status == "pending"


def test_cannot_submit_empty_or_twice_or_add_after_submit(client, patient):
    h, _ = patient()
    cid = client.post("/api/conversations", headers=h).json()["id"]
    assert client.post(f"/api/conversations/{cid}/submit", headers=h).status_code == 422
    client.post(f"/api/conversations/{cid}/messages", headers=h, json={"content": "Back pain"})
    assert client.post(f"/api/conversations/{cid}/submit", headers=h).status_code == 201
    assert client.post(f"/api/conversations/{cid}/submit", headers=h).status_code == 409
    assert client.post(f"/api/conversations/{cid}/messages", headers=h,
                       json={"content": "more"}).status_code == 409
    # A new conversation can be started afterwards.
    assert client.post("/api/conversations", headers=h).json()["id"] != cid


@pytest.mark.parametrize("bad", [
    {"content": ""}, {"content": "   "}, {"content": "x" * 4001},
    {"content": "ok", "language": "fr"}, {"content": "ok", "input_mode": "telepathy"},
    {"content": "ok", "sender": "assistant"},
])
def test_message_validation(client, patient, bad):
    h, _ = patient()
    cid = client.post("/api/conversations", headers=h).json()["id"]
    assert client.post(f"/api/conversations/{cid}/messages", headers=h, json=bad).status_code == 422


def test_withdrawn_consent_blocks_new_messages(client, patient):
    h, _ = patient()
    cid = client.post("/api/conversations", headers=h).json()["id"]
    client.post("/api/patients/me/consents", headers=h, json={**CONSENT, "granted": False})
    r = client.post(f"/api/conversations/{cid}/messages", headers=h, json={"content": "hello"})
    assert r.status_code == 403
    assert client.post("/api/conversations", headers=h).status_code == 403


def test_patient_cannot_touch_another_patients_conversation(client, patient):
    h1, _ = patient("9811100001", "Synthetic One")
    h2, _ = patient("9811100002", "Synthetic Two")
    cid = client.post("/api/conversations", headers=h1).json()["id"]
    assert client.get(f"/api/conversations/{cid}", headers=h2).status_code == 404
    assert client.post(f"/api/conversations/{cid}/messages", headers=h2,
                       json={"content": "x"}).status_code == 404
    assert client.post(f"/api/conversations/{cid}/submit", headers=h2).status_code == 404


@pytest.mark.parametrize("role", [Role.DOCTOR, Role.STAFF, Role.ADMIN])
def test_only_patients_open_conversations(client, auth_headers, role):
    assert client.post("/api/conversations", headers=auth_headers(role)).status_code == 403


# ---------- staff review ----------

def test_staff_lists_views_corrects_and_confirms(client, patient, auth_headers, db, departments):
    h, pid = patient()
    iid = _submit(client, h, (HINDI, "hi", "voice_browser"))
    s = auth_headers(Role.STAFF)

    listing = client.get("/api/intakes", params={"review_status": "pending_review"}, headers=s).json()
    assert listing["total"] == 1 and listing["items"][0]["patient_name"] == "Synthetic Intake Patient"

    view = client.get(f"/api/intakes/{iid}", headers=s).json()
    assert view["original_text"] == HINDI and view["translation_status"] == "pending"
    assert view["patient"]["id"] == pid and view["messages"][0]["content"] == HINDI

    gm = {"department_id": departments["general_medicine"]}
    # Cannot confirm a Hindi intake until someone provides English text.
    assert client.post(f"/api/intakes/{iid}/confirm", headers=s, json=gm).status_code == 422

    english = "High fever and headache since yesterday."
    r = client.patch(f"/api/intakes/{iid}", headers=s,
                     json={"final_text": english, "reason": "staff translation"})
    assert r.status_code == 200 and r.json()["final_text"] == english
    r = client.patch(f"/api/intakes/{iid}", headers=s, json={"final_text": english + " Weakness."})
    assert r.status_code == 200

    assert client.post(f"/api/intakes/{iid}/confirm", headers=s, json={}).status_code == 422  # no dept
    r = client.post(f"/api/intakes/{iid}/confirm", headers=s, json=gm)
    assert r.status_code == 200
    body = r.json()
    assert body["review_status"] == "confirmed" and body["reviewed_at"]
    assert body["original_text"] == HINDI  # original never overwritten
    revs = [(x["field"], x["old_value"], x["new_value"]) for x in body["revisions"]]
    assert revs == [
        ("final_text", None, english),
        ("final_text", english, english + " Weakness."),
        ("department", None, "General Medicine"),
        ("review_status", "pending_review", "confirmed"),
    ]
    assert body["confirmed_department"]["code"] == "general_medicine"
    assert client.post(f"/api/intakes/{iid}/confirm", headers=s, json=gm).status_code == 409
    mine = client.get("/api/patients/me/intakes", headers=h).json()[0]
    assert mine["review_status"] == "confirmed" and mine["confirmed_department_name"] == "General Medicine"

    actions = set(db.scalars(select(AuditEvent.action)).all())
    assert {"intake.submitted", "intake.viewed", "intake.corrected", "intake.confirmed"} <= actions
    # Audit details never contain the patient's words.
    blob = str(db.scalars(select(AuditEvent.details)).all())
    assert "बुखार" not in blob and "fever" not in blob


def test_confirm_english_intake_accepts_original(client, patient, auth_headers, db, departments):
    h, _ = patient()
    iid = _submit(client, h, ("Mild rash on arm.", "en", "text"))
    s = auth_headers(Role.STAFF)
    body = client.post(f"/api/intakes/{iid}/confirm", headers=s,
                       json={"department_id": departments["dermatology"]}).json()
    assert body["final_text"] == "Mild rash on arm." and body["english_text"] == "Mild rash on arm."
    assert len(db.scalars(select(IntakeRevision)).all()) == 3


def test_confirm_with_final_edit(client, patient, auth_headers, departments):
    h, _ = patient()
    iid = _submit(client, h, ("rash arm", "en", "text"))
    s = auth_headers(Role.STAFF)
    body = client.post(f"/api/intakes/{iid}/confirm", headers=s,
                       json={"final_text": "Rash on the arm.", "reason": "tidied",
                             "department_id": departments["dermatology"]}).json()
    assert body["final_text"] == "Rash on the arm." and body["original_text"] == "rash arm"


@pytest.mark.parametrize("role", [Role.PATIENT, Role.DOCTOR, Role.ADMIN])
def test_only_staff_review_intakes(client, patient, auth_headers, role):
    h, _ = patient()
    iid = _submit(client, h, ("Ear ache.", "en", "text"))
    other = auth_headers(role)
    assert client.get("/api/intakes", headers=other).status_code == 403
    assert client.get(f"/api/intakes/{iid}", headers=other).status_code == 403
    assert client.patch(f"/api/intakes/{iid}", headers=other, json={"final_text": "x"}).status_code == 403
    assert client.post(f"/api/intakes/{iid}/confirm", headers=other,
                       json={"department_id": "00000000-0000-0000-0000-000000000000"}).status_code == 403


def test_list_is_oldest_first_and_filterable(client, patient, auth_headers, departments):
    h1, _ = patient("9811100011", "Synthetic First")
    h2, _ = patient("9811100012", "Synthetic Second")
    first = _submit(client, h1, ("first", "en", "text"))
    _submit(client, h2, ("second", "en", "text"))
    s = auth_headers(Role.STAFF)
    client.post(f"/api/intakes/{first}/confirm", headers=s,
                json={"department_id": departments["general_medicine"]})
    pending = client.get("/api/intakes", params={"review_status": "pending_review"}, headers=s).json()
    assert [i["patient_name"] for i in pending["items"]] == ["Synthetic Second"]
    everything = client.get("/api/intakes", headers=s).json()
    assert [i["patient_name"] for i in everything["items"]] == ["Synthetic First", "Synthetic Second"]


def test_unknown_intake_404(client, auth_headers):
    s = auth_headers(Role.STAFF)
    assert client.get("/api/intakes/00000000-0000-0000-0000-000000000000", headers=s).status_code == 404
