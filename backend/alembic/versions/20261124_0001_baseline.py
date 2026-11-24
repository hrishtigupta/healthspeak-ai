"""Baseline: empty starting point for the HealthSpeak AI schema.

No tables yet - Phase 2 adds users and roles on top of this revision.

Revision ID: 0001
Revises:
Create Date: 2026-11-24

"""
from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
