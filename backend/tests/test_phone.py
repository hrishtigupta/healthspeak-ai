"""Adding / changing a patient's mobile number with an SMS code (synthetic data only)."""

import re
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.core.consent import CONSENT_VERSION
from app.core.enums import Role
from app.database.models import PasswordResetCode, Patient, User
from app.services import sms_service

CONSENT = {"version": CONSENT_VERSION, "granted": True, "language": "en"}
PW = "Phone-Synthetic-1"


@pytest.fixture
def sent(monkeypatch):
    box = []
    monkeypatch.setattr(sms_service, "send_sms", lambda phone, text: box.append((phone, text)))
    monkeypatch.setattr(get_settings(), "otp_resend_seconds", 0)
    return box


@pytest.fixture
def register(client):
    def _r(phone, name="Synthetic Phone Patient"):
        r = client.post("/api/patients/register", json={
            "full_name": name, "phone": phone, "date_of_birth": "1992-02-02", "gender": "other",
            "password": PW, "consent": CONSENT, "email": f"p{phone}@example.com"})
        assert r.status_code == 201, r.text
        return {"Authorization": f"Bearer {r.json()['access_token']}"}
    return _r


def code(sent):
    return re.search(r"\b(\d{6})\b", sent[-1][1]).group(1)


def wrong(c):
    return "000000" if c != "000000" else "111111"


def req(client, h, phone):
    return client.post("/api/patients/me/phone/request", headers=h, json={"phone": phone})


def confirm(client, h, c):
    return client.post("/api/patients/me/phone/confirm", headers=h, json={"code": c})


def login(client, ident, pw=PW):
    return client.post("/api/auth/login", json={"identifier": ident, "password": pw}).status_code


def test_existing_number_starts_unverified(client, register):
    h = register("9811300001")
    me = client.get("/api/patients/me", headers=h).json()
    assert me["phone"] == "+919811300001" and me["phone_verified"] is False


def test_verify_the_current_number(client, register, sent):
    h = register("9811300001")
    assert req(client, h, "9811300001").status_code == 200
    assert sent[-1][0] == "+919811300001"
    assert confirm(client, h, code(sent)).json()["phone_verified"] is True
    assert req(client, h, "9811300001").status_code == 409  # already verified


def test_change_number_old_one_stays_until_new_is_verified(client, register, sent, db):
    h = register("9811300002")
    req(client, h, "9811300002")
    confirm(client, h, code(sent))
    assert req(client, h, "9811300099").status_code == 200
    assert sent[-1][0] == "+919811300099"  # the code goes to the NEW number
    me = client.get("/api/patients/me", headers=h).json()
    assert me["phone"] == "+919811300002" and me["phone_verified"] is True  # unchanged so far
    assert login(client, "9811300002") == 200 and login(client, "9811300099") == 401

    assert confirm(client, h, wrong(code(sent))).status_code == 400
    assert client.get("/api/patients/me", headers=h).json()["phone"] == "+919811300002"  # still old

    me = confirm(client, h, code(sent)).json()
    assert me["phone"] == "+919811300099" and me["phone_verified"] is True
    assert login(client, "9811300099") == 200 and login(client, "9811300002") == 401
    assert db.scalars(select(Patient)).one().phone == "+919811300099"  # profile and login in step


def test_unverified_new_number_is_never_marked_verified(client, register, sent):
    h = register("9811300003")
    req(client, h, "9811300088")  # code requested but never entered
    me = client.get("/api/patients/me", headers=h).json()
    assert me["phone"] == "+919811300003" and me["phone_verified"] is False


def test_number_used_by_another_account_is_refused(client, register, sent):
    register("9811300010")
    h = register("9811300011", "Second Synthetic Patient")
    assert req(client, h, "9811300010").status_code == 409 and sent == []


def test_number_taken_while_code_pending_is_refused_at_confirm(client, register, sent):
    h = register("9811300012")
    req(client, h, "9811300077")
    register("9811300077", "Quick Synthetic Patient")  # someone registers it first
    assert confirm(client, h, code(sent)).status_code == 409
    assert client.get("/api/patients/me", headers=h).json()["phone"] == "+919811300012"


def test_cannot_change_another_patients_number(client, register, sent):
    a = register("9811300020")
    b = register("9811300021", "Other Synthetic Patient")
    req(client, a, "9811300055")
    assert confirm(client, b, code(sent)).status_code == 400  # codes belong to who asked for them
    assert client.get("/api/patients/me", headers=b).json()["phone"] == "+919811300021"
    assert client.get("/api/patients/me", headers=a).json()["phone"] == "+919811300020"


def test_add_number_to_account_without_one(client, register, sent, db):
    h = register("9811300030")
    db.scalars(select(User)).one().phone = None
    db.scalars(select(Patient)).one().phone = None
    db.commit()
    assert client.get("/api/patients/me", headers=h).json()["phone"] is None
    assert req(client, h, "9811300031").status_code == 200
    me = confirm(client, h, code(sent)).json()
    assert me["phone"] == "+919811300031" and me["phone_verified"] is True


def test_forgot_password_uses_the_updated_number(client, register, sent):
    h = register("9811300040")
    req(client, h, "9811300041")
    confirm(client, h, code(sent))
    sent.clear()
    r = client.post("/api/auth/password-reset/request", json={"identifier": "9811300041"})
    assert r.status_code == 202 and sent[-1][0] == "+919811300041"
    c = client.post("/api/auth/password-reset/confirm",
                    json={"identifier": "9811300041", "code": code(sent), "new_password": "New-Synthetic-22"})
    assert c.status_code == 204
    assert login(client, "9811300041", "New-Synthetic-22") == 200
    # The old number no longer identifies the account: no code is sent for it.
    sent.clear()
    assert client.post("/api/auth/password-reset/request", json={"identifier": "9811300040"}).status_code == 202
    assert sent == []


def test_invalid_number_and_bad_code_format(client, register):
    h = register("9811300050")
    assert client.post("/api/patients/me/phone/request", headers=h, json={"phone": "12"}).status_code == 422
    assert client.post("/api/patients/me/phone/confirm", headers=h, json={"code": "abc123"}).status_code == 422


def test_resend_limit_and_attempt_lock(client, register, sent, monkeypatch):
    h = register("9811300060")
    monkeypatch.setattr(get_settings(), "otp_resend_seconds", 60)
    assert req(client, h, "9811300061").status_code == 200
    assert req(client, h, "9811300061").status_code == 429
    good = code(sent)
    for _ in range(get_settings().otp_max_attempts):
        assert confirm(client, h, wrong(good)).status_code == 400
    assert confirm(client, h, good).status_code == 400  # locked after too many wrong tries


def test_expired_code_rejected(client, register, sent, db):
    h = register("9811300070")
    req(client, h, "9811300071")
    row = db.scalars(select(PasswordResetCode)).one()
    row.expires_at = row.expires_at - timedelta(minutes=30)
    db.commit()
    assert confirm(client, h, code(sent)).status_code == 400


def test_sms_not_configured_is_reported(client, register, monkeypatch):
    h = register("9811300080")
    monkeypatch.setattr(get_settings(), "sms_provider", "twilio")
    assert req(client, h, "9811300081").status_code == 503


def test_anonymous_and_staff_cannot_use_phone_endpoints(client, auth_headers):
    assert req(client, {}, "9811300090").status_code == 401
    assert req(client, auth_headers(Role.STAFF), "9811300090").status_code == 403
