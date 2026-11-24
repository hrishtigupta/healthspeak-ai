"""Login, logout, lockout and token validation."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.enums import Role
from app.core.security import hash_token
from app.database.models import AuditEvent, AuthSession, User
from tests.conftest import TEST_PASSWORD


def _login(client, identifier, password=TEST_PASSWORD):
    return client.post("/api/auth/login", json={"identifier": identifier, "password": password})


def test_login_with_email_returns_token_and_profile(client, make_user):
    make_user(Role.DOCTOR, email="Dr.Who@Example.com")
    r = _login(client, "  dr.who@EXAMPLE.com ")  # case/whitespace-insensitive
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert len(body["access_token"]) >= 40
    assert body["user"]["role"] == "doctor"
    assert body["user"]["email"] == "dr.who@example.com"
    assert "password_hash" not in body["user"]


def test_login_with_phone_in_any_format(client, make_user):
    make_user(Role.PATIENT, phone="+919876543210")
    for ident in ("9876543210", "+91 98765-43210", "0091 9876543210"):
        assert _login(client, ident).status_code == 200, ident


def test_failures_are_indistinguishable(client, make_user):
    make_user(Role.STAFF, email="staff@example.com")
    make_user(Role.STAFF, email="gone@example.com", is_active=False)
    responses = [
        _login(client, "staff@example.com", "wrong-password"),
        _login(client, "nobody@example.com"),
        _login(client, "gone@example.com"),  # correct password, inactive account
        _login(client, "not-a-phone"),
    ]
    for r in responses:
        assert r.status_code == 401
        assert r.json() == {"detail": "Invalid credentials"}


def test_lockout_after_repeated_failures(client, make_user, db):
    user = make_user(Role.PATIENT, email="lock@example.com")
    for _ in range(5):
        assert _login(client, "lock@example.com", "wrong").status_code == 401
    # Locked now: even the correct password is refused.
    assert _login(client, "lock@example.com").status_code == 401
    db.refresh(user)
    assert user.locked_until is not None
    # Once the lock expires, the correct password works again.
    user.locked_until = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()
    assert _login(client, "lock@example.com").status_code == 200


def test_successful_login_resets_failed_count(client, make_user, db):
    user = make_user(Role.PATIENT, email="reset@example.com")
    for _ in range(3):
        _login(client, "reset@example.com", "wrong")
    assert _login(client, "reset@example.com").status_code == 200
    db.refresh(user)
    assert user.failed_login_count == 0
    assert user.last_login_at is not None


def test_password_is_stored_as_argon2id(make_user, db):
    user = make_user(Role.PATIENT)
    stored = db.scalar(select(User.password_hash).where(User.id == user.id))
    assert stored.startswith("$argon2id$")
    assert TEST_PASSWORD not in stored


def test_only_token_hash_is_stored(client, make_user, db):
    make_user(Role.PATIENT, email="hash@example.com")
    token = _login(client, "hash@example.com").json()["access_token"]
    stored = db.scalars(select(AuthSession.token_hash)).all()
    assert stored == [hash_token(token)]
    assert token not in stored


def test_protected_endpoint_requires_token(client):
    r = client.get("/api/users/me")
    assert r.status_code == 401
    assert r.headers.get("www-authenticate") == "Bearer"


def test_invalid_and_malformed_tokens_rejected(client):
    for header in ("Bearer not-a-real-token", "Bearer ", "Basic abc", "garbage"):
        assert client.get("/api/users/me", headers={"Authorization": header}).status_code == 401


def test_expired_token_rejected(client, make_user, login, db):
    make_user(Role.PATIENT, email="exp@example.com")
    headers = login("exp@example.com")
    session = db.scalar(select(AuthSession))
    session.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db.commit()
    assert client.get("/api/users/me", headers=headers).status_code == 401


def test_logout_revokes_token(client, make_user, login):
    make_user(Role.PATIENT, email="out@example.com")
    headers = login("out@example.com")
    assert client.get("/api/users/me", headers=headers).status_code == 200
    assert client.post("/api/auth/logout", headers=headers).status_code == 204
    assert client.get("/api/users/me", headers=headers).status_code == 401
    assert client.post("/api/auth/logout", headers=headers).status_code == 401


def test_deactivated_user_loses_access_immediately(client, make_user, login, db):
    user = make_user(Role.STAFF, email="deact@example.com")
    headers = login("deact@example.com")
    user.is_active = False
    db.commit()
    assert client.get("/api/users/me", headers=headers).status_code == 401


def test_login_events_are_audited_without_secrets(client, make_user, db):
    user = make_user(Role.PATIENT, email="audit@example.com")
    _login(client, "audit@example.com", "wrong")
    _login(client, "unknown@example.com")
    _login(client, "audit@example.com")
    events = db.scalars(select(AuditEvent).order_by(AuditEvent.created_at)).all()
    actions = [(e.action, e.actor_user_id, (e.details or {}).get("reason")) for e in events]
    assert ("login.failed", user.id, "bad_password") in actions
    assert ("login.failed", None, "unknown_account") in actions
    assert ("login.success", user.id, None) in actions
    blob = str([(e.details, e.target_id) for e in events])
    assert "unknown@example.com" not in blob and "wrong" not in blob


def test_login_rejects_unexpected_fields(client):
    r = client.post("/api/auth/login", json={"identifier": "a@example.com", "password": "x", "role": "admin"})
    assert r.status_code == 422
