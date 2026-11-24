"""Patient self-registration, profiles, consent history and access control."""

from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.core.consent import CONSENT_VERSION
from app.core.enums import Role
from app.database.models import AuditEvent, ConsentRecord

CONSENT = {"version": CONSENT_VERSION, "granted": True, "language": "hi"}

SIGNUP = {
    "full_name": "  Synthetic   Patient ",
    "phone": "98111 22233",
    "date_of_birth": "1990-05-17",
    "gender": "female",
    "password": "Signup-Synthetic-1",
    "ui_language": "hi",
    "preferred_language": "hi",
    "consent": CONSENT,
}

WALK_IN = {
    "full_name": "Synthetic Walk In",
    "date_of_birth": "1958-01-02",
    "gender": "male",
    "phone": "+91 98000 11111",
    "preferred_language": "ur",
    "consent": {**CONSENT, "language": "ur"},
}


def _register(client, **overrides):
    return client.post("/api/patients/register", json={**SIGNUP, **overrides})


# ---------- consent text ----------

@pytest.mark.parametrize("lang", ["en", "hi", "ur"])
def test_consent_text_available_in_three_languages(client, lang):
    r = client.get("/api/consent/current", params={"language": lang})
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == CONSENT_VERSION
    assert body["language"] == lang and body["text"] and body["title"]
    assert body["is_draft"] is True


# ---------- self registration ----------

def test_self_registration_creates_account_profile_and_consent(client, db):
    r = _register(client)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["access_token"]
    assert body["user"]["role"] == "patient" and body["user"]["ui_language"] == "hi"
    p = body["patient"]
    assert p["full_name"] == "Synthetic Patient"  # whitespace tidied
    assert p["phone"] == "+919811122233"
    assert p["has_account"] is True
    assert p["consent"] == {**p["consent"], "granted": True, "version": CONSENT_VERSION,
                            "is_current_version": True}
    rec = db.scalar(select(ConsentRecord))
    assert rec.method == "self_service" and rec.language == "hi"
    # The returned token works and can read the profile.
    me = client.get("/api/patients/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200 and me.json()["id"] == p["id"]


def test_registered_patient_can_log_in_with_mobile(client):
    _register(client)
    r = client.post("/api/auth/login", json={"identifier": "9811122233", "password": SIGNUP["password"]})
    assert r.status_code == 200


def test_registration_requires_consent(client):
    r = _register(client, consent={**CONSENT, "granted": False})
    assert r.status_code == 422
    assert "Consent is required" in r.json()["detail"]


def test_registration_with_outdated_consent_version_conflicts(client):
    r = _register(client, consent={**CONSENT, "version": "old-version"})
    assert r.status_code == 409


def test_duplicate_mobile_conflicts_and_creates_nothing(client, db):
    assert _register(client).status_code == 201
    r = _register(client, full_name="Someone Else")
    assert r.status_code == 409
    assert len(db.scalars(select(ConsentRecord)).all()) == 1


@pytest.mark.parametrize("bad", [
    {"password": "short"},
    {"phone": ""},
    {"phone": "123"},
    {"date_of_birth": (date.today() + timedelta(days=1)).isoformat()},
    {"date_of_birth": "1850-01-01"},
    {"gender": "unknown"},
    {"preferred_language": "fr"},
    {"full_name": "   "},
    {"role": "admin"},
])
def test_registration_validation(client, bad):
    assert _register(client, **bad).status_code == 422


def test_registration_is_atomic_on_failure(client, db):
    # Invalid consent version -> no user, patient or consent rows left behind.
    _register(client, consent={**CONSENT, "version": "nope"})
    r = client.post("/api/auth/login", json={"identifier": "9811122233", "password": SIGNUP["password"]})
    assert r.status_code == 401


# ---------- patient's own record ----------

def test_patient_updates_own_profile_and_audit_has_no_values(client, db):
    token = _register(client).json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    r = client.patch("/api/patients/me", json={"gender": "other", "preferred_language": "en"}, headers=h)
    assert r.status_code == 200
    assert r.json()["gender"] == "other" and r.json()["preferred_language"] == "en"
    ev = db.scalar(select(AuditEvent).where(AuditEvent.action == "patient.updated"))
    assert ev.details == {"fields": ["gender", "preferred_language"]}


def test_patient_can_withdraw_and_regrant_consent(client):
    token = _register(client).json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    assert client.post("/api/patients/me/consents", json={**CONSENT, "granted": False}, headers=h).status_code == 201
    assert client.get("/api/patients/me", headers=h).json()["consent"]["granted"] is False
    assert client.post("/api/patients/me/consents", json=CONSENT, headers=h).status_code == 201
    history = client.get("/api/patients/me/consents", headers=h).json()
    assert [c["granted"] for c in history] == [True, False, True]  # append-only history


def test_patient_without_profile_gets_404(client, auth_headers):
    assert client.get("/api/patients/me", headers=auth_headers(Role.PATIENT)).status_code == 404


@pytest.mark.parametrize("role", [Role.DOCTOR, Role.STAFF, Role.ADMIN])
def test_non_patients_cannot_use_patient_me(client, auth_headers, role):
    assert client.get("/api/patients/me", headers=auth_headers(role)).status_code == 403


# ---------- staff ----------

def test_staff_registers_walk_in_and_finds_it(client, auth_headers, db):
    h = auth_headers(Role.STAFF)
    r = client.post("/api/patients", json=WALK_IN, headers=h)
    assert r.status_code == 201, r.text
    p = r.json()
    assert p["has_account"] is False and p["consent"]["granted"] is True
    assert db.scalar(select(ConsentRecord)).method == "staff_assisted"
    for q in ("walk", "9800011111", "1111"):
        found = client.get("/api/patients", params={"q": q}, headers=h).json()
        assert found["total"] == 1, q
    assert client.get("/api/patients", params={"q": "nobody"}, headers=h).json()["total"] == 0


def test_search_treats_wildcards_literally(client, auth_headers):
    h = auth_headers(Role.STAFF)
    client.post("/api/patients", json=WALK_IN, headers=h)
    assert client.get("/api/patients", params={"q": "%"}, headers=h).json()["total"] == 0


def test_staff_view_is_audited(client, auth_headers, db):
    h = auth_headers(Role.STAFF)
    pid = client.post("/api/patients", json=WALK_IN, headers=h).json()["id"]
    assert client.get(f"/api/patients/{pid}", headers=h).status_code == 200
    assert db.scalar(select(AuditEvent).where(AuditEvent.action == "patient.viewed")) is not None


def test_staff_records_consent_withdrawal_on_behalf(client, auth_headers):
    h = auth_headers(Role.STAFF)
    pid = client.post("/api/patients", json=WALK_IN, headers=h).json()["id"]
    r = client.post(f"/api/patients/{pid}/consents", json={**CONSENT, "granted": False}, headers=h)
    assert r.status_code == 201 and r.json()["method"] == "staff_assisted"
    assert client.get(f"/api/patients/{pid}", headers=h).json()["consent"]["granted"] is False
    assert len(client.get(f"/api/patients/{pid}/consents", headers=h).json()) == 2


def test_walk_in_requires_consent(client, auth_headers):
    h = auth_headers(Role.STAFF)
    r = client.post("/api/patients", json={**WALK_IN, "consent": {**CONSENT, "granted": False}}, headers=h)
    assert r.status_code == 422


def test_unknown_patient_404(client, auth_headers):
    h = auth_headers(Role.STAFF)
    assert client.get("/api/patients/00000000-0000-0000-0000-000000000000", headers=h).status_code == 404


@pytest.mark.parametrize("role", [Role.PATIENT, Role.DOCTOR, Role.ADMIN])
def test_only_staff_access_patient_records(client, auth_headers, role):
    staff_h = auth_headers(Role.STAFF)
    pid = client.post("/api/patients", json=WALK_IN, headers=staff_h).json()["id"]
    h = auth_headers(role)
    assert client.get("/api/patients", headers=h).status_code == 403
    assert client.get(f"/api/patients/{pid}", headers=h).status_code == 403
    assert client.post("/api/patients", json=WALK_IN, headers=h).status_code == 403
    assert client.patch(f"/api/patients/{pid}", json={"gender": "other"}, headers=h).status_code == 403


def test_patient_cannot_read_another_patient(client, auth_headers):
    staff_h = auth_headers(Role.STAFF)
    other = client.post("/api/patients", json=WALK_IN, headers=staff_h).json()["id"]
    token = _register(client).json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    assert client.get(f"/api/patients/{other}", headers=h).status_code == 403


def test_anonymous_gets_401(client):
    assert client.get("/api/patients").status_code == 401
    assert client.get("/api/patients/me").status_code == 401
