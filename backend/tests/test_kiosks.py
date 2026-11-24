"""Kiosk registry, heartbeats and system health (D8)."""

from datetime import timedelta

import pytest

from app.core.clock import now_utc
from app.core.enums import Role
from app.database.models import Kiosk


def register(client, admin, code="lobby-1"):
    r = client.post("/api/admin/kiosks", headers=admin, json={"code": code, "name": "Lobby kiosk",
                                                               "location": "Main entrance"})
    assert r.status_code == 201, r.text
    return r.json()


def beat(client, key, **body):
    return client.post("/api/kiosks/heartbeat", headers={"X-Kiosk-Key": key} if key else {},
                       json={"app_version": "1.0.0", "microphone": "granted", "ui_language": "hi", **body})


def test_register_shows_key_once_and_stores_only_hash(client, auth_headers, db):
    admin = auth_headers(Role.ADMIN)
    k = register(client, admin)
    assert len(k["key"]) >= 40 and k["online"] is False
    stored = db.get(Kiosk, __import__("uuid").UUID(k["id"]))
    assert stored.key_hash != k["key"] and k["key"] not in stored.key_hash
    listed = client.get("/api/admin/kiosks", headers=admin).json()
    assert "key" not in listed[0]


def test_heartbeat_marks_online_and_records_report(client, auth_headers):
    admin = auth_headers(Role.ADMIN)
    k = register(client, admin)
    assert beat(client, k["key"]).status_code == 204
    listed = client.get("/api/admin/kiosks", headers=admin).json()[0]
    assert listed["online"] is True and listed["app_version"] == "1.0.0"
    assert listed["last_report"]["microphone"] == "granted" and listed["last_report"]["ui_language"] == "hi"


def test_kiosk_goes_offline_without_heartbeats(client, auth_headers, db):
    admin = auth_headers(Role.ADMIN)
    k = register(client, admin)
    beat(client, k["key"])
    row = db.query(Kiosk).one()
    row.last_seen_at = now_utc() - timedelta(minutes=10)
    db.commit()
    assert client.get("/api/admin/kiosks", headers=admin).json()[0]["online"] is False


@pytest.mark.parametrize("key", [None, "", "not-a-real-key"])
def test_bad_kiosk_keys_rejected(client, key):
    assert beat(client, key).status_code == 401


def test_inactive_or_rotated_key_rejected(client, auth_headers):
    admin = auth_headers(Role.ADMIN)
    k = register(client, admin)
    new = client.post(f"/api/admin/kiosks/{k['id']}/rotate-key", headers=admin).json()["key"]
    assert beat(client, k["key"]).status_code == 401
    assert beat(client, new).status_code == 204
    client.patch(f"/api/admin/kiosks/{k['id']}", headers=admin, json={"is_active": False})
    assert beat(client, new).status_code == 401


def test_heartbeat_validates_body(client, auth_headers):
    k = register(client, auth_headers(Role.ADMIN))
    assert beat(client, k["key"], microphone="maybe").status_code == 422
    assert beat(client, k["key"], ui_language="fr").status_code == 422


def test_duplicate_code_and_bad_code(client, auth_headers):
    admin = auth_headers(Role.ADMIN)
    register(client, admin, "desk-2")
    assert client.post("/api/admin/kiosks", headers=admin, json={"code": "desk-2", "name": "Again"}).status_code == 409
    assert client.post("/api/admin/kiosks", headers=admin, json={"code": "Bad Code!", "name": "X"}).status_code == 422


def test_system_health(client, auth_headers):
    admin = auth_headers(Role.ADMIN)
    k = register(client, admin)
    beat(client, k["key"])
    h = client.get("/api/admin/system-health", headers=admin).json()
    assert h["database"] == "ok"
    assert {m["name"] for m in h["models"]} == {"Speech recognition", "Translation"}
    assert h["kiosks"] == {"total": 1, "online": 1, "inactive": 0}
    assert set(h["failures_last_24h"]) == {"transcriptions_failed", "intakes_translation_failed",
                                           "intakes_translation_pending"}
    assert "writable" in h["audio_storage"]


@pytest.mark.parametrize("role", [Role.PATIENT, Role.DOCTOR, Role.STAFF])
def test_kiosk_admin_is_admin_only(client, auth_headers, role):
    h = auth_headers(role)
    assert client.get("/api/admin/kiosks", headers=h).status_code == 403
    assert client.get("/api/admin/system-health", headers=h).status_code == 403
    assert client.post("/api/admin/kiosks", headers=h, json={"code": "x1", "name": "X"}).status_code == 403
