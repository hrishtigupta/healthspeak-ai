"""Migrations apply, roll back and re-apply cleanly on a throwaway database."""

import pytest
from alembic import command
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from app.database.base import Base
from tests.conftest import alembic_config


@pytest.mark.no_db
def test_upgrade_downgrade_upgrade(test_db_url):
    url = make_url(test_db_url)
    scratch = url.set(database=f"{url.database[:-len('_test')]}_migration_test")
    assert scratch.database.endswith("_test")
    scratch_str = scratch.render_as_string(hide_password=False)

    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT",
                          connect_args={"connect_timeout": 5})
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{scratch.database}" WITH (FORCE)'))
        conn.execute(text(f'CREATE DATABASE "{scratch.database}"'))
    try:
        cfg = alembic_config(scratch_str)
        command.upgrade(cfg, "head")
        eng = create_engine(scratch_str)
        expected = {t.name for t in Base.metadata.sorted_tables}
        assert expected <= set(inspect(eng).get_table_names())
        command.downgrade(cfg, "base")
        assert set(inspect(eng).get_table_names()) - {"alembic_version"} == set()
        command.upgrade(cfg, "head")
        assert expected <= set(inspect(eng).get_table_names())
        eng.dispose()
    finally:
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{scratch.database}" WITH (FORCE)'))
        admin.dispose()
