"""chat dialogue columns, phone verification

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-26 15:00:00.000000+00:00

Adds nullable columns only. Nothing is dropped or rewritten; existing phone numbers stay
"not verified" until their owner confirms them with a code.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0011'
down_revision: Union[str, None] = '0010'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("messages", sa.Column("english_text", sa.Text(), nullable=True))
    op.add_column("messages", sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("users", sa.Column("phone_verified_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("password_reset_codes", sa.Column(
        "purpose", sa.String(length=16), server_default="password_reset", nullable=False))
    op.add_column("password_reset_codes", sa.Column("new_phone", sa.String(length=16), nullable=True))


def downgrade() -> None:
    op.drop_column("password_reset_codes", "new_phone")
    op.drop_column("password_reset_codes", "purpose")
    op.drop_column("users", "phone_verified_at")
    op.drop_column("messages", "meta")
    op.drop_column("messages", "english_text")
