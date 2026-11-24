"""Rule-based extraction, traceable summaries, department suggestions (Phase 6)."""

import re

import pytest

from app.ai.department_classification import Rule, suggest
from app.ai.text_processing import extract, summarize
from app.core.consent import CONSENT_VERSION
from app.core.enums import Role

CONSENT = {"version": CONSENT_VERSION, "granted": True, "language": "en"}
FORBIDDEN = re.compile(r"\b(diagnos\w*|prescri\w*|you have|likely|probably|infection|disease)\b", re.I)


def terms(mentions):
    return [m.term for m in mentions]


# ---------- extraction: common cases ----------

def test_common_case_extracts_only_what_was_said():
    ex = extract("I have had a sore throat and a mild fever for three days. I also feel tired.")
    assert terms(ex.reported) == ["sore throat", "fever", "tiredness"]
    assert [d.text for d in ex.durations] == ["for three days"]
    assert [s.text for s in ex.severity] == ["mild"]
    # Evidence is the exact source text at the recorded position.
    src = "I have had a sore throat and a mild fever for three days. I also feel tired."
    for m in ex.reported:
        assert src[m.evidence.start:m.evidence.end] == m.evidence.text


def test_negation_is_reported_as_denied_not_as_symptom():
    ex = extract("I have a cough but no fever. I don't have chest pain or breathlessness.")
    assert terms(ex.reported) == ["cough"]
    assert terms(ex.denied) == ["fever", "chest pain", "breathing difficulty"]


def test_not_sure_is_uncertainty_not_negation():
    ex = extract("I'm not sure if I have a fever, maybe it comes and goes.")
    assert "fever" in terms(ex.reported)
    assert {u.text.lower() for u in ex.uncertainty} >= {"not sure", "maybe", "comes and goes"}


def test_specific_phrase_beats_generic_pain():
    ex = extract("Chest pain since yesterday.")
    assert terms(ex.reported) == ["chest pain"]
    assert [d.text for d in ex.durations] == ["since yesterday"]


def test_missing_information_is_listed_not_invented():
    ex = extract("I have a headache.")
    assert terms(ex.reported) == ["headache"]
    assert ex.durations == [] and ex.severity == [] and ex.medication_mentions == []
    assert "How long it has been going on (duration)" in ex.missing
    assert "Medicines being taken" in ex.missing and "Allergies" in ex.missing


def test_medication_and_allergy_quoted_verbatim():
    ex = extract("I took paracetamol this morning. I am allergic to penicillin.")
    assert ex.medication_mentions == ["I took paracetamol this morning."]
    assert ex.allergy_mentions == ["I am allergic to penicillin."]


def test_out_of_scope_text_has_no_symptoms():
    ex = extract("Where is the parking? I want to book an appointment for my mother.")
    assert ex.reported == [] and ex.denied == []
    assert ex.missing[0].startswith("No symptoms")


@pytest.mark.parametrize("text", [
    "I have had a sore throat and a mild fever for three days.",
    "no fever, no cough",
    "Chest pain and I fainted. I take tablets for blood pressure.",
    "Where is the canteen?",
])
def test_summary_quotes_sources_and_never_diagnoses(text):
    ex = extract(text)
    s = summarize(ex)
    assert "Not a diagnosis" in s and "Requires staff review" in s
    assert not FORBIDDEN.search(s.replace("Not a diagnosis", ""))
    for m in ex.reported + ex.denied:
        assert f'"{m.evidence.text}"' in s


# ---------- department suggestion ----------

RULES = [
    Rule("1", "route", "knee pain", 6, "d-ortho", "orthopaedics", "Orthopaedics"),
    Rule("2", "route", "cough", 4, "d-pulm", "pulmonology", "Pulmonology"),
    Rule("3", "route", "sore throat", 4, "d-ent", "ent", "ENT"),
    Rule("4", "attention", "chest pain", 1, None, None, None),
]
DEFAULT = ("d-gm", "general_medicine", "General Medicine")


def test_suggestion_matched_with_explanation():
    s = suggest("Knee pain when climbing stairs.", RULES, DEFAULT)
    assert s.status == "matched" and s.department_code == "orthopaedics"
    assert s.candidates[0].matches[0].evidence == "Knee pain"


def test_tie_is_ambiguous_and_staff_must_choose():
    s = suggest("Cough and sore throat.", RULES, DEFAULT)
    assert s.status == "ambiguous" and s.department_id is None
    assert {c.code for c in s.candidates} == {"pulmonology", "ent"}


def test_no_match_falls_back_to_default_labelled():
    s = suggest("I feel a bit off today.", RULES, DEFAULT)
    assert s.status == "default" and s.department_code == "general_medicine" and s.candidates == []


def test_negated_phrase_does_not_route_or_flag():
    s = suggest("No chest pain. No knee pain.", RULES, DEFAULT)
    assert s.status == "default" and s.attention == []


def test_attention_flag_with_evidence():
    s = suggest("Sudden chest pain while walking.", RULES, DEFAULT)
    assert [a.evidence for a in s.attention] == ["chest pain"]


def test_ruleset_version_changes_with_rules():
    a = suggest("cough", RULES, DEFAULT).ruleset_version
    b = suggest("cough", RULES[:-1], DEFAULT).ruleset_version
    assert a != b


# ---------- API ----------

@pytest.fixture
def patient(client):
    r = client.post("/api/patients/register", json={
        "full_name": "Synthetic Analysis Patient", "phone": "9833300000", "date_of_birth": "1970-07-07",
        "gender": "male", "password": "Analysis-Synthetic-1", "consent": CONSENT})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _submit(client, h, text, lang="en"):
    cid = client.post("/api/conversations", headers=h).json()["id"]
    client.post(f"/api/conversations/{cid}/messages", headers=h, json={"content": text, "language": lang})
    return client.post(f"/api/conversations/{cid}/submit", headers=h).json()["id"]


def test_submit_runs_analysis_and_staff_sees_it(client, patient, auth_headers, departments):
    iid = _submit(client, patient, "Sudden chest pain and palpitations since this morning.")
    s = auth_headers(Role.STAFF)
    item = client.get("/api/intakes", headers=s).json()["items"][0]
    assert item["suggested_department"] == "Cardiology" and item["needs_attention"] is True
    view = client.get(f"/api/intakes/{iid}", headers=s).json()
    a = view["analysis"]
    assert a["source"] == "english_text" and a["suggestion"]["status"] == "matched"
    assert a["suggestion"]["department_code"] == "cardiology"
    assert [x["evidence"] for x in a["suggestion"]["attention"]] == ["chest pain"]
    assert "chest pain" in [m["term"] for m in a["extraction"]["reported"]]
    assert view["review_status"] == "pending_review"  # suggestion never auto-confirms


def test_patient_never_sees_ai_suggestion(client, patient, auth_headers, departments):
    _submit(client, patient, "Knee pain for two weeks.")
    mine = client.get("/api/patients/me/intakes", headers=patient).json()[0]
    assert mine["confirmed_department_name"] is None
    assert "analysis" not in mine and "suggestion" not in str(mine)


def test_staff_can_reanalyse_reviewed_text(client, patient, auth_headers, departments):
    iid = _submit(client, patient, "pain", "en")
    s = auth_headers(Role.STAFF)
    client.patch(f"/api/intakes/{iid}", headers=s, json={"final_text": "Toothache for 3 days."})
    view = client.post(f"/api/intakes/{iid}/analyse", headers=s, json={"source": "final_text"}).json()
    assert view["analysis"]["source"] == "final_text"
    assert view["analysis"]["suggestion"]["department_code"] == "dental"


def test_hindi_intake_without_translation_has_no_analysis(client, patient, auth_headers, departments):
    iid = _submit(client, patient, "मुझे बुखार है।", "hi")
    s = auth_headers(Role.STAFF)
    view = client.get(f"/api/intakes/{iid}", headers=s).json()
    assert view["analysis"] is None
    r = client.post(f"/api/intakes/{iid}/analyse", headers=s, json={"source": "english_text"})
    assert r.status_code == 422


def test_confirm_with_inactive_or_unknown_department_rejected(client, patient, auth_headers, departments):
    iid = _submit(client, patient, "Rash on my arm.")
    s, a = auth_headers(Role.STAFF), auth_headers(Role.ADMIN)
    client.patch(f"/api/admin/departments/{departments['dermatology']}", headers=a, json={"is_active": False})
    r = client.post(f"/api/intakes/{iid}/confirm", headers=s, json={"department_id": departments["dermatology"]})
    assert r.status_code == 422


# ---------- admin configuration ----------

def test_admin_adds_rule_and_it_changes_suggestion(client, patient, auth_headers, departments):
    a = auth_headers(Role.ADMIN)
    r = client.post("/api/admin/routing-rules", headers=a, json={
        "kind": "route", "phrase": "  Sugar   Levels ", "weight": 9, "department_id": departments["general_medicine"]})
    assert r.status_code == 201 and r.json()["phrase"] == "sugar levels"
    iid = _submit(client, patient, "My sugar levels are high.")
    view = client.get(f"/api/intakes/{iid}", headers=auth_headers(Role.STAFF)).json()
    sug = view["analysis"]["suggestion"]
    assert sug["department_code"] == "general_medicine" and sug["status"] == "matched"


def test_admin_deactivates_rule(client, auth_headers, departments):
    a = auth_headers(Role.ADMIN)
    rules = client.get("/api/admin/routing-rules", headers=a, params={"kind": "attention"}).json()
    chest = next(r for r in rules if r["phrase"] == "chest pain")
    assert client.patch(f"/api/admin/routing-rules/{chest['id']}", headers=a,
                        json={"is_active": False}).json()["is_active"] is False


def test_only_one_default_department(client, auth_headers, departments):
    a = auth_headers(Role.ADMIN)
    client.patch(f"/api/admin/departments/{departments['ent']}", headers=a, json={"is_default": True})
    defaults = [d for d in client.get("/api/admin/departments", headers=a).json() if d["is_default"]]
    assert [d["code"] for d in defaults] == ["ent"]


@pytest.mark.parametrize("bad", [
    {"kind": "route", "phrase": "x", "weight": 5},                      # no department, too short
    {"kind": "route", "phrase": "valid", "weight": 11, "department_id": None},
    {"kind": "attention", "phrase": "valid", "weight": 1,
     "department_id": "00000000-0000-0000-0000-000000000001"},           # attention with dept
    {"kind": "maybe", "phrase": "valid", "weight": 1},
])
def test_invalid_rules_rejected(client, auth_headers, departments, bad):
    assert client.post("/api/admin/routing-rules", headers=auth_headers(Role.ADMIN), json=bad).status_code == 422


def test_duplicate_department_code_conflicts(client, auth_headers, departments):
    r = client.post("/api/admin/departments", headers=auth_headers(Role.ADMIN),
                    json={"code": "cardiology", "name": "Cardiology again"})
    assert r.status_code == 409


@pytest.mark.parametrize("role", [Role.PATIENT, Role.DOCTOR, Role.STAFF])
def test_only_admin_configures(client, auth_headers, departments, role):
    h = auth_headers(role)
    assert client.get("/api/admin/routing-rules", headers=h).status_code == 403
    assert client.post("/api/admin/departments", headers=h, json={"code": "abc", "name": "Abc"}).status_code == 403


def test_department_list_for_workforce_not_patients(client, auth_headers, departments):
    assert client.get("/api/departments", headers=auth_headers(Role.STAFF)).status_code == 200
    assert client.get("/api/departments", headers=auth_headers(Role.PATIENT)).status_code == 403
