"""Administrator-only user management and role enforcement."""

import pytest

from app.core.enums import Role

NEW_USER = {
    "full_name": "Synthetic Nurse",
    "email": "nurse@example.com",
    "password": "Another-Synthetic-1",
    "role": "staff",
}


@pytest.mark.parametrize("role", [Role.PATIENT, Role.DOCTOR, Role.STAFF])
def test_non_admins_are_forbidden(client, auth_headers, role):
    h = auth_headers(role)
    assert client.get("/api/admin/users", headers=h).status_code == 403
    assert client.post("/api/admin/users", json=NEW_USER, headers=h).status_code == 403


def test_anonymous_gets_401_not_403(client):
    assert client.get("/api/admin/users").status_code == 401
    assert client.post("/api/admin/users", json=NEW_USER).status_code == 401


def test_admin_can_list_users(client, auth_headers, make_user):
    h = auth_headers(Role.ADMIN)
    make_user(Role.PATIENT)
    make_user(Role.DOCTOR)
    r = client.get("/api/admin/users", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3
    assert all("password_hash" not in u for u in body["items"])
    only_doctors = client.get("/api/admin/users", params={"role": "doctor"}, headers=h).json()
    assert only_doctors["total"] == 1 and only_doctors["items"][0]["role"] == "doctor"


def test_admin_creates_user_who_can_then_log_in(client, auth_headers):
    h = auth_headers(Role.ADMIN)
    r = client.post("/api/admin/users", json={**NEW_USER, "phone": "98765 00000"}, headers=h)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["role"] == "staff" and body["phone"] == "+919876500000"
    login = client.post("/api/auth/login", json={"identifier": "nurse@example.com",
                                                 "password": NEW_USER["password"]})
    assert login.status_code == 200


def test_duplicate_email_or_phone_conflicts(client, auth_headers):
    h = auth_headers(Role.ADMIN)
    assert client.post("/api/admin/users", json=NEW_USER, headers=h).status_code == 201
    dup = client.post("/api/admin/users", json={**NEW_USER, "email": "NURSE@example.com"}, headers=h)
    assert dup.status_code == 409


@pytest.mark.parametrize("bad", [
    {**NEW_USER, "password": "short"},
    {**NEW_USER, "role": "superuser"},
    {**NEW_USER, "email": "not-an-email"},
    {**NEW_USER, "email": None},  # neither email nor phone
    {**NEW_USER, "phone": "12"},
    {**NEW_USER, "full_name": "   "},
    {**NEW_USER, "is_active": False},  # unexpected field
])
def test_invalid_create_payloads_rejected(client, auth_headers, bad):
    h = auth_headers(Role.ADMIN)
    assert client.post("/api/admin/users", json=bad, headers=h).status_code == 422
