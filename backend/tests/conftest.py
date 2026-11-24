"""Shared pytest fixtures.

Tests run against a SEPARATE database (default "<your db>_test") so your
development data is never touched. It is created and migrated automatically;
every table is emptied before each test.
"""

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.core.enums import Role, UiLanguage
from app.database.base import Base
from app.database.models import User
from app.database.session import get_db
from app.main import app
from app.services import user_service

BACKEND_DIR = Path(__file__).resolve().parents[1]
TEST_PASSWORD = "Synthetic-Test-Pass-1"


def _test_db_url() -> str:
    s = get_settings()
    if s.test_database_url:
        return s.test_database_url
    url = make_url(s.database_url)
    return url.set(database=f"{url.database}_test").render_as_string(hide_password=False)


def _ensure_database(url_str: str) -> None:
    url = make_url(url_str)
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT",
                          connect_args={"connect_timeout": 5})
    with admin.connect() as conn:
        exists = conn.scalar(text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": url.database})
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    admin.dispose()


def alembic_config(url: str) -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.attributes["database_url"] = url
    return cfg


@pytest.fixture(scope="session")
def test_db_url() -> str:
    url = _test_db_url()
    name = make_url(url).database or ""
    # Safety: never run destructive test cleanup against a non-test database.
    assert name.endswith("_test"), f"Refusing to use non-test database {name!r} for tests"
    return url


@pytest.fixture(scope="session")
def engine(test_db_url):
    _ensure_database(test_db_url)
    command.upgrade(alembic_config(test_db_url), "head")
    eng = create_engine(test_db_url, connect_args={"connect_timeout": 5})
    yield eng
    eng.dispose()


@pytest.fixture(scope="session")
def session_factory(engine):
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture(autouse=True)
def _clean_tables(request, engine):
    """Empty every app table before each test (only runs on the *_test database)."""
    if "no_db" in request.keywords:
        yield
        return
    tables = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    if tables:
        with engine.begin() as conn:
            conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    yield


def _models_not_installed():
    from app.ai.model_loader import EngineUnavailable

    raise EngineUnavailable("test: real model not loaded")


@pytest.fixture(autouse=True)
def _isolate_ai(monkeypatch, tmp_path):
    """By default tests never touch real models and write audio to a temp folder.

    Tests that want AI behaviour install fakes with `fake_ai`, or opt into the
    real models (see test_speech.py::test_real_whisper...).
    """
    from app.ai.model_loader import asr_slot, translation_slot

    for slot in (asr_slot, translation_slot):
        slot.reset()
        monkeypatch.setattr(slot, "_factory", _models_not_installed)
    monkeypatch.setattr(get_settings(), "audio_storage_dir", str(tmp_path / "audio"))
    yield
    for slot in (asr_slot, translation_slot):
        slot.reset()


@pytest.fixture
def db(session_factory) -> Iterator[Session]:
    with session_factory() as s:
        yield s


@pytest.fixture
def client(session_factory) -> Iterator[TestClient]:
    def _get_test_db():
        s = session_factory()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _get_test_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def make_user(db) -> Callable[..., User]:
    counter = {"n": 0}

    def _make(role: Role = Role.PATIENT, *, password: str = TEST_PASSWORD, email: str | None = None,
              phone: str | None = None, ui_language: UiLanguage = UiLanguage.EN,
              is_active: bool = True, full_name: str | None = None) -> User:
        counter["n"] += 1
        n = counter["n"]
        if email is None and phone is None:
            email = f"{role.value}{n}@example.com"
        user = user_service.create_user(
            db, full_name=full_name or f"Test {role.value.title()} {n}", password=password,
            role=role, email=email, phone=phone, ui_language=ui_language,
        )
        if not is_active:
            user.is_active = False
            db.commit()
        return user

    return _make


@pytest.fixture
def login(client) -> Callable[..., dict]:
    """Log in and return Authorization headers."""

    def _login(identifier: str, password: str = TEST_PASSWORD) -> dict:
        r = client.post("/api/auth/login", json={"identifier": identifier, "password": password})
        assert r.status_code == 200, r.text
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    return _login


@pytest.fixture
def auth_headers(make_user, login) -> Callable[..., dict]:
    """Create a user with the given role and return their auth headers."""

    def _h(role: Role = Role.PATIENT, **kw) -> dict:
        u = make_user(role, **kw)
        return login(u.email or u.phone)

    return _h
