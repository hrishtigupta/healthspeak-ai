"""Persisted symptoms, staff review, returning-patient history, and access control.

All names, phones and statements are synthetic.
"""

import uuid

import pytest
from sqlalchemy import select

from app.ai import translation_checks
from app.core.consent import CONSENT_VERSION
from app.core.enums import Role
from app.database.models import AuditEvent, ExtractedSymptom, IntakeAnalysis, IntakeRecord, IntakeRevision

CONSENT = {"version": CONSENT_VERSION, "granted": True, "language": "en"}


def register(client, name, phone, dob="1980-01-01"):
    r = client.post("/api/patients/register", json={
        "full_name": name, "phone": phone, "date_of_birth": dob, "gender": "female",
        "password": "History-Synthetic-1", "consent": CONSENT})
    assert r.status_code == 201, r.text
    body = r.json()
    return {"Authorization": f"Bearer {body['access_token']}"}, body["patient"]["id"]


def submit(client, h, text, lang="en"):
    cid = client.post("/api/conversations", headers=h).json()["id"]
    r = client.post(f"/api/conversations/{cid}/messages", headers=h, json={"content": text, "language": lang})
    assert r.status_code == 201, r.text
    return client.post(f"/api/conversations/{cid}/submit", headers=h).json()["id"]


def staff_view(client, s, iid):
    r = client.get(f"/api/intakes/{iid}", headers=s)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture
def staff(auth_headers):
    return auth_headers(Role.STAFF)


@pytest.fixture
def ana(client, departments):
    return register(client, "Synthetic Ana Verma", "9811100001")


# ---------- persisted symptoms ----------

def test_symptoms_are_persisted_with_context_and_evidence(client, ana, staff, db):
    iid = submit(client, ana[0], "I had fever last week and now I have a cough. My mother has a headache.")
    syms = {s["term"]: s for s in staff_view(client, staff, iid)["symptoms"]}
    assert syms["fever"]["status"] == "historical" and syms["cough"]["status"] == "current"
    assert syms["headache"]["status"] == "third_party" and syms["headache"]["subject"] == "third_party"
    assert syms["cough"]["evidence_text"] == "cough"
    assert syms["cough"]["review_status"] == "unreviewed" and syms["cough"]["symptom_code"] == "hs.cough"
    rows = db.scalars(select(ExtractedSymptom).where(ExtractedSymptom.intake_id == uuid.UUID(iid))).all()
    assert len(rows) == 3 and all(r.patient_id == uuid.UUID(ana[1]) for r in rows)


def test_attributes_are_stored_on_the_symptom(client, ana, staff):
    iid = submit(client, ana[0], "Severe headache every morning for three days.")
    s = staff_view(client, staff, iid)["symptoms"][0]
    assert s["attributes"]["severity"]["text"] == "Severe"
    assert s["attributes"]["duration"]["text"] == "for three days"


def test_analysis_exposes_review_reasons_and_unmatched_text(client, ana, staff):
    iid = submit(client, ana[0], "I have a cough. There is a strange pressure behind my eye.")
    ex = staff_view(client, staff, iid)["analysis"]["extraction"]
    assert [u["text"] for u in ex["unmatched"]] == ["There is a strange pressure behind my eye"]
    assert ex["review_required"] is True and ex["review_reasons"]


# ---------- staff review ----------

def test_confirm_reject_correct_keep_ai_reading_and_are_audited(client, ana, staff, db):
    iid = submit(client, ana[0], "I have a cough and a rash. I might have a fever.")
    syms = {s["term"]: s for s in staff_view(client, staff, iid)["symptoms"]}
    base = f"/api/intakes/{iid}/symptoms"

    r = client.post(f"{base}/{syms['cough']['id']}/review", headers=staff, json={"action": "confirm"})
    assert r.status_code == 200 and r.json()["review_status"] == "confirmed"

    r = client.post(f"{base}/{syms['rash']['id']}/review", headers=staff,
                    json={"action": "reject", "note": "patient meant the cough"})
    assert r.json()["review_status"] == "rejected" and r.json()["review_note"] == "patient meant the cough"

    r = client.post(f"{base}/{syms['fever']['id']}/review", headers=staff,
                    json={"action": "correct", "status": "current", "note": "patient confirmed in person"})
    body = r.json()
    assert body["review_status"] == "corrected"
    assert body["status"] == "uncertain" and body["effective_status"] == "current"  # AI value kept
    assert body["reviewed_by_user_id"] and body["reviewed_at"]

    revisions = db.scalars(select(IntakeRevision).where(IntakeRevision.field == "symptom")).all()
    assert len(revisions) == 3 and all(r.edited_by_user_id for r in revisions)
    assert any('"review": "unreviewed"' in (r.old_value or "") for r in revisions)
    actions = {a.action for a in db.scalars(select(AuditEvent))}
    assert {"symptom.confirm", "symptom.reject", "symptom.correct"} <= actions


def test_staff_can_add_a_missed_symptom(client, ana, staff):
    iid = submit(client, ana[0], "There is a strange pressure behind my eye.")
    r = client.post(f"/api/intakes/{iid}/symptoms", headers=staff, json={
        "term": "Eye Pressure", "status": "current", "evidence_text": "strange pressure behind my eye"})
    assert r.status_code == 201
    s = r.json()
    assert s["term"] == "eye pressure" and s["match_type"] == "staff" and s["review_status"] == "confirmed"


def test_invalid_review_requests_are_rejected(client, ana, staff):
    iid = submit(client, ana[0], "I have a cough.")
    sid = staff_view(client, staff, iid)["symptoms"][0]["id"]
    url = f"/api/intakes/{iid}/symptoms/{sid}/review"
    assert client.post(url, headers=staff, json={"action": "correct"}).status_code == 422
    assert client.post(url, headers=staff, json={"action": "confirm", "term": "x"}).status_code == 422
    assert client.post(url, headers=staff, json={"action": "delete"}).status_code == 422
    assert client.post(url, headers=staff, json={"action": "correct", "status": "bogus"}).status_code == 422
    assert client.post(url, headers=staff, json={"action": "confirm", "extra": 1}).status_code == 422
    other = uuid.uuid4()
    assert client.post(f"/api/intakes/{iid}/symptoms/{other}/review", headers=staff,
                       json={"action": "confirm"}).status_code == 404


def test_symptom_cannot_be_reviewed_through_another_intake(client, ana, staff):
    first = submit(client, ana[0], "I have a cough.")
    second = submit(client, ana[0], "I have a rash.")
    sid = staff_view(client, staff, first)["symptoms"][0]["id"]
    r = client.post(f"/api/intakes/{second}/symptoms/{sid}/review", headers=staff, json={"action": "confirm"})
    assert r.status_code == 404


def test_confirmed_intake_symptoms_are_locked(client, ana, staff, departments):
    iid = submit(client, ana[0], "I have a cough.")
    sid = staff_view(client, staff, iid)["symptoms"][0]["id"]
    assert client.post(f"/api/intakes/{iid}/confirm", headers=staff,
                       json={"department_id": departments["pulmonology"]}).status_code == 200
    assert client.post(f"/api/intakes/{iid}/symptoms/{sid}/review", headers=staff,
                       json={"action": "reject"}).status_code == 409
    assert client.post(f"/api/intakes/{iid}/symptoms", headers=staff,
                       json={"term": "fever"}).status_code == 409


def test_reanalysis_keeps_staff_decisions_and_old_ai_rows(client, ana, staff, db):
    iid = submit(client, ana[0], "I have a cough.")
    sid = staff_view(client, staff, iid)["symptoms"][0]["id"]
    client.post(f"/api/intakes/{iid}/symptoms/{sid}/review", headers=staff, json={"action": "confirm"})
    client.post(f"/api/intakes/{iid}/symptoms", headers=staff, json={"term": "eye pressure"})
    view = client.post(f"/api/intakes/{iid}/analyse", headers=staff, json={"source": "english_text"}).json()
    by_term = {s["term"]: s for s in view["symptoms"]}
    assert by_term["cough"]["review_status"] == "confirmed" and by_term["cough"]["id"] != sid
    assert by_term["eye pressure"]["review_status"] == "confirmed"
    # the first analysis and its rows still exist (append-only)
    assert db.scalar(select(IntakeAnalysis).where(IntakeAnalysis.intake_id == uuid.UUID(iid))
                     .order_by(IntakeAnalysis.created_at).limit(1))
    assert db.get(ExtractedSymptom, uuid.UUID(sid)) is not None
    # an old symptom id is now superseded
    r = client.post(f"/api/intakes/{iid}/symptoms/{sid}/review", headers=staff, json={"action": "reject"})
    assert r.status_code == 409


def test_confirming_records_whether_staff_followed_the_suggestion(client, ana, staff, departments, db):
    iid = submit(client, ana[0], "Knee pain for two weeks.")
    client.post(f"/api/intakes/{iid}/confirm", headers=staff,
                json={"department_id": departments["general_medicine"]})
    ev = db.scalar(select(AuditEvent).where(AuditEvent.action == "intake.confirmed"))
    assert ev.details["suggested"] == "orthopaedics" and ev.details["followed_suggestion"] is False


# ---------- returning patient ----------

def _first_visit(client, ana, staff, departments):
    first = submit(client, ana[0], "Headache for three days. I took paracetamol. I am allergic to penicillin.")
    sid = next(s["id"] for s in staff_view(client, staff, first)["symptoms"] if s["term"] == "headache")
    client.post(f"/api/intakes/{first}/symptoms/{sid}/review", headers=staff, json={"action": "confirm"})
    client.post(f"/api/intakes/{first}/confirm", headers=staff,
                json={"department_id": departments["neurology"]})
    return first


def test_returning_patient_history_is_shown_with_dates_and_labels(client, ana, staff, departments):
    first = _first_visit(client, ana, staff, departments)
    second = submit(client, ana[0], "I have a headache and a cough since this morning.")
    r = client.get(f"/api/intakes/{second}/history", headers=staff)
    assert r.status_code == 200, r.text
    h = r.json()
    assert h["patient_id"] == ana[1] and h["total"] == 1 and "NOT be assumed" in h["notice"]
    enc = h["encounters"][0]
    assert enc["intake_id"] == first and enc["encounter_date"]
    assert enc["confirmed_department"] == "Neurology"
    sym = next(s for s in enc["symptoms"] if s["term"] == "headache")
    assert sym["source"] == "staff_confirmed" and sym["details"]["duration"] == "for three days"
    # medicines / allergies are quoted from the patient and are history, not facts about today
    assert any("paracetamol" in m for m in enc["medication_mentions"])
    assert any("penicillin" in m for m in enc["allergy_mentions"])
    # the repeated symptom is highlighted as context
    assert [x["term"] for x in h["recurring"]] == ["headache"]
    assert h["recurring"][0]["previous"][0]["source"] == "staff_confirmed"


def test_unconfirmed_ai_reading_is_labelled_differently(client, ana, staff, departments):
    submit(client, ana[0], "I have a rash.")
    second = submit(client, ana[0], "Rash again.")
    enc = client.get(f"/api/intakes/{second}/history", headers=staff).json()["encounters"][0]
    assert [s["source"] for s in enc["symptoms"]] == ["ai_unconfirmed"]


def test_new_encounter_is_separate_and_old_one_unchanged(client, ana, staff, departments, db):
    first = _first_visit(client, ana, staff, departments)
    before = staff_view(client, staff, first)
    rec = db.get(IntakeRecord, uuid.UUID(first))
    snap = (rec.original_text, rec.final_text, rec.review_status, rec.confirmed_department_id,
            len(rec.analyses), len(rec.revisions))

    second = submit(client, ana[0], "I have a cough.")
    assert second != first
    db.expire_all()
    rec = db.get(IntakeRecord, uuid.UUID(first))
    assert snap == (rec.original_text, rec.final_text, rec.review_status, rec.confirmed_department_id,
                    len(rec.analyses), len(rec.revisions))
    after = staff_view(client, staff, first)
    assert after["symptoms"] == before["symptoms"] and after["original_text"] == before["original_text"]
    # the new encounter's own record holds only what was said in the new encounter
    new = staff_view(client, staff, second)
    assert [s["term"] for s in new["symptoms"]] == ["cough"]
    assert "headache" not in new["original_text"]


def test_history_of_an_earlier_visit_does_not_include_later_visits(client, ana, staff, departments):
    first = _first_visit(client, ana, staff, departments)
    submit(client, ana[0], "I have a cough.")
    h = client.get(f"/api/intakes/{first}/history", headers=staff).json()
    assert h["total"] == 0 and h["encounters"] == []


def test_similar_names_never_merge(client, staff, departments):
    a = register(client, "Synthetic Sam Rao", "9811100010", "1990-05-05")
    b = register(client, "Synthetic Sam Rao", "9811100011", "1990-05-05")  # same name and birth date
    c = register(client, "Synthetic Sam Raoo", "9811100012", "1990-05-05")  # near-identical name
    a_visit = submit(client, a[0], "I have a toothache.")
    b_visit = submit(client, b[0], "I have a cough.")
    c_visit = submit(client, c[0], "I have a rash.")
    for visit in (a_visit, b_visit, c_visit):
        assert client.get(f"/api/intakes/{visit}/history", headers=staff).json()["total"] == 0
    assert client.get(f"/api/patients/{a[1]}/history", headers=staff).json()["total"] == 1
    assert client.get(f"/api/patients/{b[1]}/history", headers=staff).json()["total"] == 1
    terms = [s["term"] for e in client.get(f"/api/patients/{a[1]}/history", headers=staff).json()["encounters"]
             for s in e["symptoms"]]
    assert terms == ["toothache"]


def test_history_is_paginated_newest_first(client, ana, staff, departments):
    ids = [submit(client, ana[0], f"I have a cough. Visit {n}.") for n in range(4)]
    h = client.get(f"/api/patients/{ana[1]}/history", headers=staff, params={"limit": 2}).json()
    assert h["total"] == 4 and [e["intake_id"] for e in h["encounters"]] == [ids[3], ids[2]]
    h2 = client.get(f"/api/patients/{ana[1]}/history", headers=staff, params={"limit": 2, "offset": 2}).json()
    assert [e["intake_id"] for e in h2["encounters"]] == [ids[1], ids[0]]
    for bad in ({"limit": 0}, {"limit": 51}, {"offset": -1}):
        assert client.get(f"/api/patients/{ana[1]}/history", headers=staff, params=bad).status_code == 422


def test_rejected_and_third_party_symptoms_are_not_history(client, ana, staff, departments):
    first = submit(client, ana[0], "I have a rash and a cough. My mother has a headache.")
    sid = next(s["id"] for s in staff_view(client, staff, first)["symptoms"] if s["term"] == "rash")
    client.post(f"/api/intakes/{first}/symptoms/{sid}/review", headers=staff, json={"action": "reject"})
    second = submit(client, ana[0], "Follow-up.")
    terms = [s["term"] for s in client.get(f"/api/intakes/{second}/history", headers=staff)
             .json()["encounters"][0]["symptoms"]]
    assert terms == ["cough"]


def test_history_views_are_audited(client, ana, staff, db):
    first = submit(client, ana[0], "I have a cough.")
    client.get(f"/api/intakes/{first}/history", headers=staff)
    client.get(f"/api/patients/{ana[1]}/history", headers=staff)
    events = db.scalars(select(AuditEvent).where(AuditEvent.action == "patient.history_viewed")).all()
    assert len(events) == 2 and {e.target_id for e in events} == {ana[1]}


# ---------- access control ----------

def test_patient_sees_only_own_confirmed_history(client, staff, departments):
    a = register(client, "Synthetic Pia Nair", "9811100020")
    b = register(client, "Synthetic Raj Nair", "9811100021")
    a_first = submit(client, a[0], "I have a cough.")
    sid = staff_view(client, staff, a_first)["symptoms"][0]["id"]
    client.post(f"/api/intakes/{a_first}/symptoms/{sid}/review", headers=staff, json={"action": "confirm"})
    client.post(f"/api/intakes/{a_first}/confirm", headers=staff,
                json={"department_id": departments["pulmonology"]})
    submit(client, a[0], "I have a rash.")
    submit(client, b[0], "I have a toothache.")

    mine = client.get("/api/patients/me/history", headers=a[0]).json()
    assert mine["total"] == 2
    text = str(mine)
    assert "toothache" not in text  # never another patient's data
    confirmed = {s["term"] for e in mine["encounters"] for s in e["confirmed_symptoms"]}
    assert confirmed == {"cough"}  # the unconfirmed AI "rash" reading is not shown
    assert "ai_suggested_department" not in text and "suggestion" not in text
    assert "toothache" in str(client.get("/api/patients/me/history", headers=b[0]).json())


def test_patient_cannot_read_anyones_history_through_staff_endpoints(client, staff):
    a = register(client, "Synthetic Uma Das", "9811100030")
    b = register(client, "Synthetic Vik Das", "9811100031")
    b_visit = submit(client, b[0], "I have a cough.")
    for url in (f"/api/patients/{b[1]}/history", f"/api/patients/{a[1]}/history",
                f"/api/intakes/{b_visit}/history"):
        assert client.get(url, headers=a[0]).status_code == 403
    assert client.post(f"/api/intakes/{b_visit}/symptoms", headers=a[0], json={"term": "fever"}).status_code == 403


def test_unauthenticated_access_is_denied(client, ana):
    visit = submit(client, ana[0], "I have a cough.")
    for url in (f"/api/patients/{ana[1]}/history", f"/api/intakes/{visit}/history", "/api/patients/me/history"):
        assert client.get(url).status_code == 401
    assert client.post(f"/api/intakes/{visit}/symptoms", json={"term": "fever"}).status_code == 401


@pytest.mark.parametrize("role", [Role.DOCTOR, Role.ADMIN])
def test_other_roles_have_no_history_access_yet(client, ana, auth_headers, role):
    visit = submit(client, ana[0], "I have a cough.")
    h = auth_headers(role)
    assert client.get(f"/api/patients/{ana[1]}/history", headers=h).status_code == 403
    assert client.get(f"/api/intakes/{visit}/history", headers=h).status_code == 403
    assert client.get("/api/patients/me/history", headers=h).status_code == 403


def test_unknown_ids_are_404(client, staff):
    assert client.get(f"/api/patients/{uuid.uuid4()}/history", headers=staff).status_code == 404
    assert client.get(f"/api/intakes/{uuid.uuid4()}/history", headers=staff).status_code == 404


def test_audit_log_never_contains_patient_text(client, ana, staff, db):
    visit = submit(client, ana[0], "I have a cough and I am allergic to penicillin.")
    sid = staff_view(client, staff, visit)["symptoms"][0]["id"]
    client.post(f"/api/intakes/{visit}/symptoms/{sid}/review", headers=staff, json={"action": "confirm"})
    client.get(f"/api/intakes/{visit}/history", headers=staff)
    blob = " ".join(str(e.details) for e in db.scalars(select(AuditEvent)))
    assert "penicillin" not in blob and "cough" not in blob


# ---------- typed, voice and translated input ----------

def test_typed_and_voice_transcript_take_the_same_pipeline(client, staff, departments):
    from tests.test_speech import FakeASR, tone_wav, upload
    from app.ai.model_loader import asr_slot

    text = "I do not have fever. I have a headache since this morning."
    typed = register(client, "Synthetic Typed Patient", "9811100040")
    voice = register(client, "Synthetic Voice Patient", "9811100041")
    typed_visit = submit(client, typed[0], text)

    cid = client.post("/api/conversations", headers=voice[0]).json()["id"]
    asr_slot.override(FakeASR(text))
    tr = upload(client, voice[0], cid, tone_wav(), language="en").json()
    client.post(f"/api/conversations/{cid}/messages", headers=voice[0], json={
        "content": tr["text"], "language": "en", "input_mode": "voice_server", "transcription_id": tr["id"]})
    voice_visit = client.post(f"/api/conversations/{cid}/submit", headers=voice[0]).json()["id"]

    def shape(visit):
        v = staff_view(client, staff, visit)
        return ([(s["term"], s["status"]) for s in v["symptoms"]], v["analysis"]["suggestion"]["department_code"])

    assert shape(typed_visit) == shape(voice_visit)
    assert shape(typed_visit)[0] == [("fever", "negated"), ("headache", "current")]
    assert shape(typed_visit)[1] == "neurology"


def test_hindi_transcript_original_is_preserved_next_to_translation(client, staff, departments, db):
    from tests.test_speech import FakeTranslator
    from app.ai.model_loader import translation_slot

    h, _ = register(client, "Synthetic Hindi Patient", "9811100050")
    hindi = "मुझे बुखार नहीं है। सिर में दर्द है।"
    translation_slot.override(FakeTranslator())  # prefixes "[EN] ": the negation survives in the original
    iid = submit(client, h, hindi, "hi")
    rec = db.get(IntakeRecord, uuid.UUID(iid))
    assert rec.original_text == hindi and rec.original_language == "hi"
    assert rec.english_text == f"[EN] {hindi}" and rec.english_text != rec.original_text
    ex = staff_view(client, staff, iid)["analysis"]["extraction"]
    assert any("machine translation" in r for r in ex["review_reasons"])
    # the fake keeps the Hindi text, so the English side has no negation word: flagged for staff
    assert ex["translation_warnings"] and "negation" in ex["translation_warnings"][0]


# ---------- translation checks ----------

def test_translation_check_flags_lost_negation():
    out = translation_checks.check("मुझे बुखार नहीं है", "I have a fever")
    assert out == [translation_checks.NEGATION_WARNING]


def test_translation_check_accepts_kept_negation_and_numbers():
    assert translation_checks.check("मुझे 3 दिन से बुखार नहीं है", "I have had no fever for three days") == []
    assert translation_checks.check("مجھے بخار نہیں ہے", "I do not have a fever") == []


def test_translation_check_flags_lost_number_including_other_script_digits():
    assert translation_checks.check("मुझे ३ दिन से दर्द है", "I have had pain for a few days") == [
        translation_checks.NUMBER_WARNING]
    assert translation_checks.check("मुझे ३ दिन से दर्द है", "pain for 3 days") == []
