"""Tests for the /api/health endpoints."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.database.session import SessionLocal, get_db
from app.main import app

client = TestClient(app)


def test_api_health_ok():
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["version"]


class _BrokenSession:
    def execute(self, *args, **kwargs):
        raise OperationalError("SELECT 1", {}, Exception("password=secret host=db"))


def test_db_health_returns_503_without_leaking_details():
    app.dependency_overrides[get_db] = lambda: _BrokenSession()
    try:
        r = client.get("/api/health/db")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 503
    assert r.json() == {"detail": "Database unavailable"}
    assert "secret" not in r.text


def _database_reachable() -> bool:
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        return True
    except OperationalError:
        return False


@pytest.mark.integration
def test_db_health_against_real_database():
    if not _database_reachable():
        pytest.skip("PostgreSQL is not running (start it with: docker compose up -d)")
    r = client.get("/api/health/db")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "database": "connected"}
