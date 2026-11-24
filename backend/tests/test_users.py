"""Own profile and independent UI-language preferences."""

from app.core.enums import Role, UiLanguage


def test_me_returns_own_profile_without_secrets(client, make_user, login):
    make_user(Role.STAFF, email="me@example.com", full_name="Synthetic Staff")
    r = client.get("/api/users/me", headers=login("me@example.com"))
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == "me@example.com"
    assert body["full_name"] == "Synthetic Staff"
    assert body["role"] == "staff"
    for secret in ("password_hash", "failed_login_count", "locked_until"):
        assert secret not in body


def test_language_preference_is_saved_and_restored_after_login(client, make_user, login):
    make_user(Role.PATIENT, email="lang@example.com")
    h = login("lang@example.com")
    r = client.patch("/api/users/me/preferences", json={"ui_language": "ur"}, headers=h)
    assert r.status_code == 200 and r.json()["ui_language"] == "ur"
    client.post("/api/auth/logout", headers=h)
    again = client.post("/api/auth/login", json={"identifier": "lang@example.com",
                                                 "password": "Synthetic-Test-Pass-1"})
    assert again.json()["user"]["ui_language"] == "ur"


def test_patient_language_does_not_change_doctor_language(client, make_user, login):
    make_user(Role.PATIENT, email="p@example.com", ui_language=UiLanguage.EN)
    make_user(Role.DOCTOR, email="d@example.com", ui_language=UiLanguage.EN)
    hp, hd = login("p@example.com"), login("d@example.com")
    client.patch("/api/users/me/preferences", json={"ui_language": "ur"}, headers=hp)
    client.patch("/api/users/me/preferences", json={"ui_language": "hi"}, headers=hd)
    assert client.get("/api/users/me", headers=hp).json()["ui_language"] == "ur"
    assert client.get("/api/users/me", headers=hd).json()["ui_language"] == "hi"


def test_invalid_language_rejected(client, auth_headers):
    h = auth_headers(Role.PATIENT)
    for bad in ({"ui_language": "fr"}, {"ui_language": ""}, {}, {"ui_language": "en", "role": "admin"}):
        assert client.patch("/api/users/me/preferences", json=bad, headers=h).status_code == 422


def test_preferences_require_login(client):
    assert client.patch("/api/users/me/preferences", json={"ui_language": "hi"}).status_code == 401
