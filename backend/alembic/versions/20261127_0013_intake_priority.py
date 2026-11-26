"""saved Urgent / Normal priority on intake records

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-27 09:00:00.000000+00:00

Additive only. Five new columns on intake_records; no row is deleted and no existing column changes.
Every existing record gets the safe default ('normal', set by the system). Records whose latest stored
analysis already raised an "attention" (emergency) flag are then marked 'urgent', so history is not
misreported as Normal. Downgrade drops only the new columns and constraints.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0013'
down_revision: Union[str, None] = '0012'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("intake_records", sa.Column("priority", sa.String(length=8), server_default="normal",
                                              nullable=False))
    op.add_column("intake_records", sa.Column("priority_source", sa.String(length=8), server_default="system",
                                              nullable=False))
    op.add_column("intake_records", sa.Column("priority_reason", sa.Text(), nullable=True))
    op.add_column("intake_records", sa.Column("priority_changed_by_user_id", sa.Uuid(), nullable=True))
    op.add_column("intake_records", sa.Column("priority_changed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key(op.f("fk_intake_records_priority_changed_by_user_id_users"), "intake_records", "users",
                          ["priority_changed_by_user_id"], ["id"], ondelete="SET NULL")
    op.create_check_constraint(op.f("ck_intake_records_priority_valid"), "intake_records",
                               "priority IN ('urgent', 'normal')")
    op.create_check_constraint(op.f("ck_intake_records_priority_source_valid"), "intake_records",
                               "priority_source IN ('system', 'staff')")
    # Existing urgent cases (the latest analysis already flagged them) keep their urgency.
    op.execute("""
        UPDATE intake_records i SET priority = 'urgent'
        WHERE EXISTS (
            SELECT 1 FROM intake_analyses a
            WHERE a.intake_id = i.id AND a.needs_attention
              AND a.created_at = (SELECT max(created_at) FROM intake_analyses WHERE intake_id = i.id)
        )""")
    op.create_index("ix_intake_records_priority_created", "intake_records", ["priority", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_intake_records_priority_created", table_name="intake_records")
    op.drop_constraint(op.f("ck_intake_records_priority_source_valid"), "intake_records", type_="check")
    op.drop_constraint(op.f("ck_intake_records_priority_valid"), "intake_records", type_="check")
    op.drop_constraint(op.f("fk_intake_records_priority_changed_by_user_id_users"), "intake_records",
                       type_="foreignkey")
    for col in ("priority_changed_at", "priority_changed_by_user_id", "priority_reason", "priority_source",
                "priority"):
        op.drop_column("intake_records", col)
