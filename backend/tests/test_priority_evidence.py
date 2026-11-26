"""Saved Urgent / Normal priority and per-field evidence ("confidence") on intake records.
All data is synthetic."""

import uuid

import pytest
from sqlalchemy import select

from app.core.consent import CONSENT_VERSION
from app.core.enums import Role
from app.database.models import AuditEvent, IntakeRecord
from app.services.evidence import symptom_evidence

CONSENT = {"version": CONSENT_VERSION, "granted": True, "language": "en"}
_phone = iter(range(9855500000, 9855599999))


def make_patient(client):
    r = client.post("/api/patients/register", json={
        "full_name": "Synthetic Priority Patient", "phone": str(next(_phone)), "date_of_birth": "1991-01-01",
        "gender": "female", "password": "Priority-Synthetic-1", "consent": CONSENT})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def intake_from(client, h, *messages, lang="en"):
    """Run a conversation and submit it. Returns the intake id."""
    cid = client.post("/api/conversations", headers=h).json()["id"]
    for m in messages:
        r = client.post(f"/api/conversations/{cid}/messages", headers=h, json={"content": m, "language": lang})
        assert r.status_code == 201, r.text
    r = client.post(f"/api/conversations/{cid}/submit", headers=h)
    assert r.status_code == 201, r.text
    return r.json()["id"]


@pytest.fixture
def env(client, departments, auth_headers):
    class E:
        pass

    e = E()
    e.client, e.departments = client, departments
    e.staff = auth_headers(Role.STAFF)
    e.view = lambda iid: client.get(f"/api/intakes/{iid}", headers=e.staff).json()
    e.new = lambda *m, **kw: intake_from(client, make_patient(client), *m, **kw)
    return e


# ---------------------------------------------------------------- priority

def test_ordinary_intake_is_normal(env):
    d = env.view(env.new("I have a mild fever since yesterday"))
    assert d["priority"] == "normal" and d["priority_source"] == "system" and d["priority_reason"] is None


def test_emergency_symptom_makes_the_intake_urgent(env):
    d = env.view(env.new("I have severe chest pain since this morning"))
    assert d["priority"] == "urgent" and d["priority_source"] == "system"
    assert "Emergency" in d["priority_reason"] or "emergency" in d["priority_reason"]


def test_priority_is_saved_and_survives_a_refetch(env):
    iid = env.new("I cannot breathe properly and feel faint")
    assert env.view(iid)["priority"] == "urgent"
    assert env.view(iid)["priority"] == "urgent"  # read again: it is stored, not recomputed
    items = env.client.get("/api/intakes", headers=env.staff).json()["items"]
    assert next(i for i in items if i["id"] == iid)["priority"] == "urgent"


def test_queue_shows_priority_and_lists_urgent_first(env):
    normal = env.new("I have a mild sore throat")
    urgent = env.new("I have crushing chest pain")  # submitted LATER than the normal one
    items = env.client.get("/api/intakes?review_status=pending_review", headers=env.staff).json()["items"]
    ids = [i["id"] for i in items]
    assert ids.index(urgent) < ids.index(normal)  # urgent first even though newer
    by_id = {i["id"]: i for i in items}
    assert by_id[urgent]["priority"] == "urgent" and by_id[normal]["priority"] == "normal"


def test_urgent_from_the_chat_even_when_translation_is_unavailable(env):
    iid = env.new("मुझे सीने में दर्द है", lang="hi")  # no translation model in tests
    d = env.view(iid)
    assert d["translation_status"] == "pending" and d["priority"] == "urgent"


def test_department_suggestion_or_confirmation_never_lowers_priority(env):
    iid = env.new("I have chest pain and a headache")
    d = env.view(iid)
    assert d["priority"] == "urgent"
    # staff confirm an ordinary department: the emergency flag is untouched
    r = env.client.post(f"/api/intakes/{iid}/confirm", headers=env.staff,
                        json={"department_id": env.departments["general_medicine"]})
    assert r.status_code == 200 and r.json()["priority"] == "urgent"


def test_reanalysis_cannot_silently_downgrade_urgent(env):
    iid = env.new("I have severe chest pain")
    assert env.view(iid)["priority"] == "urgent"
    # staff rewrite the text to something harmless and re-run the analysis: the flag stays
    env.client.patch(f"/api/intakes/{iid}", headers=env.staff, json={"final_text": "Mild cold since two days."})
    r = env.client.post(f"/api/intakes/{iid}/analyse", headers=env.staff, json={"source": "final_text"})
    assert r.status_code == 200 and r.json()["priority"] == "urgent"


def test_staff_can_change_priority_with_a_reason_and_it_is_audited(env, db):
    iid = env.new("I have chest pain")
    r = env.client.patch(f"/api/intakes/{iid}/priority", headers=env.staff,
                         json={"priority": "normal", "reason": "Patient says it was old pain, reviewed."})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["priority"] == "normal" and body["priority_source"] == "staff"
    assert body["priority_reason"] == "Patient says it was old pain, reviewed."
    assert body["priority_changed_by_user_id"] and body["priority_changed_at"]
    rev = [x for x in body["revisions"] if x["field"] == "priority"]
    assert [(x["old_value"], x["new_value"]) for x in rev] == [("urgent", "normal")]
    assert "intake.priority_changed" in set(db.scalars(select(AuditEvent.action)).all())
    # the system never re-raises over a staff decision, even if the analysis runs again
    env.client.post(f"/api/intakes/{iid}/analyse", headers=env.staff, json={"source": "english_text"})
    assert env.view(iid)["priority"] == "normal"
    # staff can raise it again too
    r = env.client.patch(f"/api/intakes/{iid}/priority", headers=env.staff,
                         json={"priority": "urgent", "reason": "Symptoms got worse on the phone."})
    assert r.json()["priority"] == "urgent"


def test_changing_priority_needs_a_reason_and_staff_rights(env, client):
    iid = env.new("I have a mild fever")
    url = f"/api/intakes/{iid}/priority"
    assert client.patch(url, headers=env.staff, json={"priority": "urgent"}).status_code == 422  # no reason
    assert client.patch(url, headers=env.staff, json={"priority": "urgent", "reason": " "}).status_code == 422
    assert client.patch(url, headers=env.staff, json={"priority": "bogus", "reason": "because"}).status_code == 422
    assert client.patch(url, json={"priority": "urgent", "reason": "because"}).status_code == 401
    patient = make_patient(client)
    assert client.patch(url, headers=patient, json={"priority": "urgent", "reason": "because"}).status_code == 403
    assert client.patch(f"/api/intakes/{uuid.uuid4()}/priority", headers=env.staff,
                        json={"priority": "urgent", "reason": "because"}).status_code == 404


def test_existing_rows_get_the_safe_default(env, db):
    iid = env.new("I have a mild fever")
    row = db.get(IntakeRecord, uuid.UUID(iid))
    assert row.priority == "normal" and row.priority_source == "system"


# ---------------------------------------------------------------- evidence (confidence)

def test_unit_evidence_labels():
    base = dict(status="current", term="fever", effective_term="fever")
    assert symptom_evidence(match_type="exact", review_status="unreviewed", **base)["label"] == "Exact match"
    assert symptom_evidence(match_type="fuzzy", review_status="unreviewed", **base)["label"] == "Possible match"
    staff = symptom_evidence(match_type="staff", review_status="unreviewed", **base)
    assert staff["level"] == "staff" and staff["label"] == "Added or corrected by staff"
    fixed = symptom_evidence(match_type="exact", review_status="corrected", status="current", term="cough",
                             effective_term="fever")
    assert fixed["level"] == "staff" and "'cough'" in fixed["notes"][0] and "'fever'" in fixed["notes"][0]
    conf = symptom_evidence(match_type="fuzzy", review_status="confirmed", **base)
    assert conf["level"] == "possible" and conf["confirmed_by_staff"] is True  # still shows how it was found
    assert symptom_evidence(match_type="exact", review_status="rejected", **base)["level"] == "rejected"
    unsure = symptom_evidence(match_type="exact", review_status="unreviewed", status="uncertain",
                              term="fever", effective_term="fever")
    assert any("unsure" in n for n in unsure["notes"])


def _fields(d):
    return {f["field"]: f for f in d["field_evidence"]}


def test_exact_match_is_labelled_exact_per_symptom_and_field(env):
    d = env.view(env.new("I have had a mild headache for three days"))
    s = next(x for x in d["symptoms"] if x["term"] == "headache")
    assert s["evidence"]["level"] == "exact" and s["evidence"]["label"] == "Exact match"
    f = _fields(d)
    assert f["symptoms"]["level"] == "exact"
    assert f["duration"]["level"] == "exact" and "three days" in f["duration"]["detail"]
    assert f["severity"]["level"] == "exact" and "mild" in f["severity"]["detail"]


def test_fuzzy_match_is_labelled_possible(env):
    d = env.view(env.new("I have vomitng and a fever"))
    by_term = {x["term"]: x for x in d["symptoms"]}
    assert by_term["vomiting"]["match_type"] == "fuzzy" and by_term["vomiting"]["evidence"]["level"] == "possible"
    assert by_term["fever"]["evidence"]["level"] == "exact"
    assert _fields(d)["symptoms"]["level"] == "possible"  # the field needing a look wins


def test_missing_fields_are_shown_clearly(env):
    d = env.view(env.new("I have a headache"))
    f = _fields(d)
    assert f["duration"]["level"] == "missing" and f["duration"]["label"] == "Not found"
    assert f["severity"]["level"] == "missing"
    assert f["medicines"]["level"] == "missing" and f["allergies"]["level"] == "missing"
    d2 = env.view(env.new("Follow-up."))  # no symptom at all
    assert _fields(d2)["symptoms"]["level"] == "missing"


def test_no_invented_percentages(env):
    d = env.view(env.new("I have a fever"))
    text = str(d["field_evidence"]) + str([s["evidence"] for s in d["symptoms"]])
    assert "%" not in text and "probab" not in text.lower() and "confidence" not in text.lower()


def test_staff_added_symptom_is_not_presented_as_ai_extraction(env):
    iid = env.new("I have a fever")
    r = env.client.post(f"/api/intakes/{iid}/symptoms", headers=env.staff, json={"term": "cough"})
    assert r.status_code == 201, r.text
    added = r.json()
    assert added["match_type"] == "staff"
    assert added["evidence"]["level"] == "staff" and added["evidence"]["label"] == "Added or corrected by staff"
    assert "not an AI extraction" in added["evidence"]["notes"][0]
    d = env.view(iid)
    assert "added or corrected by staff" in _fields(d)["symptoms"]["detail"].lower()
    ai = next(x for x in d["symptoms"] if x["term"] == "fever")
    assert ai["evidence"]["level"] == "exact"  # the AI's own finding keeps its own label


def test_staff_correction_is_labelled_and_keeps_what_the_ai_read(env):
    iid = env.new("I have a fever")
    sid = env.view(iid)["symptoms"][0]["id"]
    r = env.client.post(f"/api/intakes/{iid}/symptoms/{sid}/review", headers=env.staff,
                        json={"action": "correct", "term": "chills"})
    assert r.status_code == 200, r.text
    ev = r.json()["evidence"]
    assert ev["level"] == "staff" and "'fever'" in ev["notes"][0] and "'chills'" in ev["notes"][0]


def test_staff_confirmation_keeps_the_original_evidence_label(env):
    iid = env.new("I have vomitng")
    sid = env.view(iid)["symptoms"][0]["id"]
    r = env.client.post(f"/api/intakes/{iid}/symptoms/{sid}/review", headers=env.staff,
                        json={"action": "confirm"})
    ev = r.json()["evidence"]
    assert ev["level"] == "possible" and ev["confirmed_by_staff"] is True
