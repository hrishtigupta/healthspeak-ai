"""Tests for the /api/health endpoints."""

from sqlalchemy.exc import OperationalError

from app.database.session import get_db
from app.main import app


def test_api_health_ok(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["version"]


class _BrokenSession:
    def execute(self, *args, **kwargs):
        raise OperationalError("SELECT 1", {}, Exception("password=secret host=db"))


def test_db_health_returns_503_without_leaking_details(client):
    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = lambda: _BrokenSession()
    try:
        r = client.get("/api/health/db")
    finally:
        app.dependency_overrides[get_db] = previous
    assert r.status_code == 503
    assert r.json() == {"detail": "Database unavailable"}
    assert "secret" not in r.text


def test_db_health_against_real_database(client):
    r = client.get("/api/health/db")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "database": "connected"}
