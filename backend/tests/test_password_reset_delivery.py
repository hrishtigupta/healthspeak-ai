"""Forgot-password delivery honesty: never claim "sent" when SMS cannot be delivered, and the
development-only on-screen code (never outside development)."""

import re

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.core.enums import Role
from app.database.models import PasswordResetCode
from app.services import sms_service

PHONE = "9876500001"
NEW_PW = "brand-new-pass-1"


def _req(client, ident=PHONE):
    return client.post("/api/auth/password-reset/request", json={"identifier": ident})


def _confirm(client, code, ident=PHONE, pw=NEW_PW):
    return client.post("/api/auth/password-reset/confirm",
                       json={"identifier": ident, "code": code, "new_password": pw})


def test_not_configured_sms_is_reported_not_faked(client, make_user, monkeypatch):
    make_user(Role.PATIENT, phone=PHONE)
    monkeypatch.setattr(get_settings(), "sms_provider", "twilio")  # selected, but no credentials
    r = _req(client)
    assert r.status_code == 503 and "not available" in r.json()["detail"]


def test_same_503_for_unknown_numbers_so_nothing_leaks(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "sms_provider", "twilio")
    assert _req(client, "9000000042").status_code == 503


def test_provider_failure_is_reported_to_the_user(client, make_user, monkeypatch):
    make_user(Role.PATIENT, phone=PHONE)

    def refuse(phone, text):
        raise sms_service.SmsNotSent("provider said no")

    monkeypatch.setattr(sms_service, "send_sms", refuse)
    r = _req(client)
    assert r.status_code == 503 and "could not send" in r.json()["detail"]


def test_failed_send_leaves_no_usable_code(client, make_user, monkeypatch, db):
    make_user(Role.PATIENT, phone=PHONE)

    def refuse(phone, text):
        raise sms_service.SmsNotSent("x")

    monkeypatch.setattr(sms_service, "send_sms", refuse)
    _req(client)
    rows = list(db.scalars(select(PasswordResetCode)))
    assert rows and all(row.used_at is not None for row in rows)


def test_dev_mode_shows_code_on_screen_and_it_really_works(client, make_user, monkeypatch, capsys):
    monkeypatch.setattr(get_settings(), "app_env", "development")
    monkeypatch.setattr(get_settings(), "sms_provider", "console")
    make_user(Role.PATIENT, phone=PHONE)
    body = _req(client).json()
    assert re.fullmatch(r"\d{6}", body["dev_code"]) and "Development mode" in body["dev_notice"]
    assert body["dev_code"] in capsys.readouterr().out  # also printed in the API window
    assert _confirm(client, "000000" if body["dev_code"] != "000000" else "111111").status_code == 400
    assert _confirm(client, body["dev_code"]).status_code == 204  # real verification, not a bypass


@pytest.mark.parametrize("env,provider", [("production", "twilio"), ("staging", "console"),
                                          ("development", "twilio")])
def test_dev_code_never_returned_outside_development_console(client, make_user, monkeypatch, env, provider):
    make_user(Role.PATIENT, phone=PHONE)
    monkeypatch.setattr(sms_service, "send_sms", lambda p, t: None)
    s = get_settings()
    for name, value in (("app_env", env), ("sms_provider", provider), ("twilio_account_sid", "ACtest"),
                        ("twilio_auth_token", "t"), ("twilio_from_number", "+10000000000")):
        monkeypatch.setattr(s, name, value)
    r = _req(client)
    assert r.status_code == 202 and "dev_code" not in r.json()


def test_console_provider_is_not_ready_in_production(monkeypatch):
    monkeypatch.setattr(get_settings(), "app_env", "production")
    monkeypatch.setattr(get_settings(), "sms_provider", "console")
    assert sms_service.status().ready is False and sms_service.dev_echo_allowed() is False


def test_dev_echo_can_be_switched_off(client, make_user, monkeypatch):
    monkeypatch.setattr(get_settings(), "app_env", "development")
    monkeypatch.setattr(get_settings(), "sms_provider", "console")
    monkeypatch.setattr(get_settings(), "dev_otp_echo", False)
    make_user(Role.PATIENT, phone=PHONE)
    assert "dev_code" not in _req(client).json()


def test_number_typed_with_spaces_and_country_code_finds_the_account(client, make_user, monkeypatch):
    sent = []
    monkeypatch.setattr(sms_service, "send_sms", lambda p, t: sent.append(p))
    make_user(Role.PATIENT, phone=PHONE)
    assert _req(client, "+91 98765 00001").status_code == 202 and sent == ["+91" + PHONE]
