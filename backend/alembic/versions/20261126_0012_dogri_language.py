"""allow Dogri ("doi") as a language value

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-26 18:00:00.000000+00:00

Only the six CHECK constraints that list language codes are replaced, each with the old list plus
'doi'. No row is read, changed or deleted. Downgrade is refused while any 'doi' row exists, so it can
never destroy or invalidate data.
"""
from typing import Sequence, Union

from alembic import op

revision: str = '0012'
down_revision: Union[str, None] = '0011'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (table, column). Earlier migrations named these constraints in slightly different styles, so the
# real name is looked up in the database instead of being guessed.
TARGETS = [
    ("users", "ui_language"),
    ("patients", "preferred_language"),
    ("consent_records", "language"),
    ("messages", "language"),
    ("intake_records", "original_language"),
    ("audio_transcriptions", "language"),
]


def _language_check_name(table: str, column: str) -> str:
    rows = op.get_bind().exec_driver_sql(
        "SELECT c.conname FROM pg_constraint c WHERE c.contype = 'c' "
        "AND c.conrelid = %s::regclass AND pg_get_constraintdef(c.oid) LIKE %s",
        (table, f"%{column}%'en'%")).fetchall()
    if len(rows) != 1:
        raise RuntimeError(f"Expected exactly one language CHECK on {table}.{column}, found {len(rows)}.")
    return rows[0][0]


def _swap(languages: str) -> None:
    for table, column in TARGETS:
        old = _language_check_name(table, column)
        op.drop_constraint(op.f(old), table, type_="check")
        op.create_check_constraint(op.f(old), table, f"{column} IN ({languages})")


def upgrade() -> None:
    _swap("'en', 'hi', 'ur', 'doi'")


def downgrade() -> None:
    conn = op.get_bind()
    for table, column in TARGETS:
        n = conn.exec_driver_sql(f"SELECT count(*) FROM {table} WHERE {column} = 'doi'").scalar()
        if n:
            raise RuntimeError(f"Cannot downgrade: {n} row(s) in {table}.{column} use 'doi'. "
                               "Nothing was changed.")
    _swap("'en', 'hi', 'ur'")
