"""Forgot-password by one-time code (patients only)."""

import re
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.core.enums import Role
from app.database.models import PasswordResetCode
from app.services import sms_service

PHONE = "9876500001"
NEW_PW = "brand-new-pass-1"


@pytest.fixture
def sent(monkeypatch):
    """Capture SMS messages instead of sending them."""
    box: list[tuple[str, str]] = []
    monkeypatch.setattr(sms_service, "send_sms", lambda phone, text: box.append((phone, text)))
    return box


def _code(sent) -> str:
    return re.search(r"\b(\d{6})\b", sent[-1][1]).group(1)


def _req(client, ident=PHONE):
    return client.post("/api/auth/password-reset/request", json={"identifier": ident})


def _confirm(client, code, ident=PHONE, pw=NEW_PW):
    return client.post("/api/auth/password-reset/confirm",
                       json={"identifier": ident, "code": code, "new_password": pw})


def test_full_reset_flow(client, make_user, sent):
    make_user(Role.PATIENT, phone=PHONE)
    assert _req(client).status_code == 202
    assert len(sent) == 1 and sent[0][0] == "+91" + PHONE
    assert _confirm(client, _code(sent)).status_code == 204
    r = client.post("/api/auth/login", json={"identifier": PHONE, "password": NEW_PW})
    assert r.status_code == 200


def test_old_password_stops_working_and_code_is_single_use(client, make_user, sent):
    make_user(Role.PATIENT, phone=PHONE)
    _req(client)
    code = _code(sent)
    assert _confirm(client, code).status_code == 204
    assert client.post("/api/auth/login", json={"identifier": PHONE, "password": "x" * 10}).status_code == 401
    assert _confirm(client, code, pw="another-pass-22").status_code == 400


def test_unknown_account_looks_identical_and_sends_nothing(client, sent):
    a = _req(client, "9000000099")
    assert a.status_code == 202 and sent == []


def test_staff_accounts_cannot_use_online_reset(client, make_user, sent):
    make_user(Role.STAFF, phone="9876500002")
    assert _req(client, "9876500002").status_code == 202
    assert sent == []


def test_wrong_code_locks_after_max_attempts(client, make_user, sent):
    make_user(Role.PATIENT, phone=PHONE)
    _req(client)
    good = _code(sent)
    bad = "000000" if good != "000000" else "111111"
    for _ in range(get_settings().otp_max_attempts):
        assert _confirm(client, bad).status_code == 400
    # Even the right code no longer works: the user must request a new one.
    assert _confirm(client, good).status_code == 400


def test_expired_code_rejected(client, make_user, sent, db):
    make_user(Role.PATIENT, phone=PHONE)
    _req(client)
    row = db.scalars(select(PasswordResetCode)).one()
    row.expires_at = row.expires_at - timedelta(minutes=30)
    db.commit()
    assert _confirm(client, _code(sent)).status_code == 400


def test_resend_is_throttled_and_new_code_cancels_old(client, make_user, sent, db, monkeypatch):
    make_user(Role.PATIENT, phone=PHONE)
    _req(client)
    _req(client)  # inside the resend window: no second SMS
    assert len(sent) == 1
    monkeypatch.setattr(get_settings(), "otp_resend_seconds", 0)
    first = _code(sent)
    _req(client)
    assert len(sent) == 2
    second = _code(sent)
    if first != second:
        assert _confirm(client, first).status_code == 400
    assert _confirm(client, second).status_code == 204


def test_reset_signs_out_other_sessions_and_clears_lockout(client, make_user, login, sent):
    user = make_user(Role.PATIENT, phone=PHONE)
    headers = login(user.phone)
    for _ in range(get_settings().login_max_failed_attempts):
        client.post("/api/auth/login", json={"identifier": PHONE, "password": "wrong-password"})
    assert client.post("/api/auth/login", json={"identifier": PHONE, "password": NEW_PW}).status_code == 401
    _req(client)
    assert _confirm(client, _code(sent)).status_code == 204
    assert client.get("/api/users/me", headers=headers).status_code == 401
    assert client.post("/api/auth/login", json={"identifier": PHONE, "password": NEW_PW}).status_code == 200


def test_code_is_stored_hashed_and_never_audited(client, make_user, sent, db):
    make_user(Role.PATIENT, phone=PHONE)
    _req(client)
    code = _code(sent)
    row = db.scalars(select(PasswordResetCode)).one()
    assert code not in row.code_hash
    from app.database.models import AuditEvent
    assert all(code not in str(e.details) for e in db.scalars(select(AuditEvent)))


def test_console_provider_refused_in_production(monkeypatch):
    monkeypatch.setattr(get_settings(), "app_env", "production")
    monkeypatch.setattr(get_settings(), "sms_provider", "console")
    with pytest.raises(sms_service.SmsNotSent):
        sms_service.send_sms("+919876500001", "x")


def test_bad_code_format_rejected(client):
    assert _confirm(client, "12ab56").status_code == 422
