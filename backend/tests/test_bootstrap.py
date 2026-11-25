"""First-run setup for a fresh (production) database. Synthetic data only."""

from sqlalchemy import select

from app.bootstrap import bootstrap
from app.core.enums import Role
from app.database.models import Department, User


def test_bootstrap_creates_admin_and_departments_but_no_demo_users(db):
    done = bootstrap(db, email="admin@hospital.example", name="Synthetic Admin", password="Synthetic-Test-Pass-1")
    assert done["admin_created"] and done["departments_loaded"] > 0
    users = db.scalars(select(User)).all()
    assert [u.role for u in users] == [Role.ADMIN.value]
    assert db.scalar(select(Department.id).limit(1))


def test_bootstrap_twice_changes_nothing(db):
    bootstrap(db, email="admin@hospital.example", name="Synthetic Admin", password="Synthetic-Test-Pass-1")
    again = bootstrap(db, email="other@hospital.example", name="Other", password="Another-Synthetic-Pass-2")
    assert again.get("admin_exists") and not again["admin_created"] and again["departments_loaded"] == 0
    assert len(db.scalars(select(User)).all()) == 1


def test_bootstrap_admin_can_log_in(client, db):
    bootstrap(db, email="admin@hospital.example", name="Synthetic Admin", password="Synthetic-Test-Pass-1")
    r = client.post("/api/auth/login", json={"identifier": "admin@hospital.example",
                                             "password": "Synthetic-Test-Pass-1"})
    assert r.status_code == 200 and r.json()["user"]["role"] == "admin"


def test_short_password_is_refused_and_nothing_is_created(db):
    import pytest
    with pytest.raises(ValueError):
        bootstrap(db, email="admin@hospital.example", name="Synthetic Admin", password="short")
    assert db.scalar(select(User.id).limit(1)) is None


def test_settings_can_read_a_different_env_file(tmp_path, monkeypatch):
    import importlib

    from app.core import config

    f = tmp_path / "demo.env"
    f.write_text("APP_ENV=production\nCORS_ORIGINS=https://demo.example.netlify.app\n", encoding="utf-8")
    monkeypatch.setenv("HEALTHSPEAK_ENV_FILE", str(f))
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    try:
        importlib.reload(config)
        s = config.Settings()
        assert s.app_env == "production" and s.cors_origin_list == ["https://demo.example.netlify.app"]
    finally:
        monkeypatch.delenv("HEALTHSPEAK_ENV_FILE", raising=False)
        importlib.reload(config)
