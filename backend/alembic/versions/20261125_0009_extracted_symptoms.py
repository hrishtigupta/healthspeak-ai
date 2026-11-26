"""extracted symptoms with staff review

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-25 10:00:00.000000+00:00

Adds one table. Nothing existing is altered or dropped, and no data is copied:
analyses made before this migration keep their JSON; re-running an analysis
creates the normalised rows.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0009'
down_revision: Union[str, None] = '0008'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_STATUSES = "'current', 'uncertain', 'negated', 'historical', 'third_party'"


def upgrade() -> None:
    op.create_table('extracted_symptoms',
    sa.Column('analysis_id', sa.Uuid(), nullable=False),
    sa.Column('intake_id', sa.Uuid(), nullable=False),
    sa.Column('patient_id', sa.Uuid(), nullable=False),
    sa.Column('term', sa.String(length=60), nullable=False),
    sa.Column('symptom_code', sa.String(length=80), nullable=True),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('subject', sa.String(length=16), nullable=False),
    sa.Column('match_type', sa.String(length=8), nullable=False),
    sa.Column('evidence_text', sa.Text(), nullable=True),
    sa.Column('evidence_start', sa.Integer(), nullable=True),
    sa.Column('evidence_end', sa.Integer(), nullable=True),
    sa.Column('attributes', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('review_status', sa.String(length=12), nullable=False),
    sa.Column('confirmed_term', sa.String(length=60), nullable=True),
    sa.Column('confirmed_status', sa.String(length=16), nullable=True),
    sa.Column('review_note', sa.String(length=500), nullable=True),
    sa.Column('reviewed_by_user_id', sa.Uuid(), nullable=True),
    sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('clock_timestamp()'), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.CheckConstraint(f"status IN ({_STATUSES})", name=op.f('ck_extracted_symptoms_status_valid')),
    sa.CheckConstraint("match_type IN ('exact', 'fuzzy', 'staff')", name=op.f('ck_extracted_symptoms_match_type_valid')),
    sa.CheckConstraint("review_status IN ('unreviewed', 'confirmed', 'corrected', 'rejected')", name=op.f('ck_extracted_symptoms_review_status_valid')),
    sa.CheckConstraint(f"confirmed_status IS NULL OR confirmed_status IN ({_STATUSES})", name=op.f('ck_extracted_symptoms_confirmed_status_valid')),
    sa.ForeignKeyConstraint(['analysis_id'], ['intake_analyses.id'], name=op.f('fk_extracted_symptoms_analysis_id_intake_analyses'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['intake_id'], ['intake_records.id'], name=op.f('fk_extracted_symptoms_intake_id_intake_records'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], name=op.f('fk_extracted_symptoms_patient_id_patients'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['reviewed_by_user_id'], ['users.id'], name=op.f('fk_extracted_symptoms_reviewed_by_user_id_users'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_extracted_symptoms'))
    )
    op.create_index(op.f('ix_extracted_symptoms_analysis_id'), 'extracted_symptoms', ['analysis_id'], unique=False)
    op.create_index(op.f('ix_extracted_symptoms_intake_id'), 'extracted_symptoms', ['intake_id'], unique=False)
    op.create_index(op.f('ix_extracted_symptoms_patient_id'), 'extracted_symptoms', ['patient_id'], unique=False)
    op.create_index('ix_extracted_symptoms_patient_term', 'extracted_symptoms', ['patient_id', 'term'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_extracted_symptoms_patient_term', table_name='extracted_symptoms')
    op.drop_index(op.f('ix_extracted_symptoms_patient_id'), table_name='extracted_symptoms')
    op.drop_index(op.f('ix_extracted_symptoms_intake_id'), table_name='extracted_symptoms')
    op.drop_index(op.f('ix_extracted_symptoms_analysis_id'), table_name='extracted_symptoms')
    op.drop_table('extracted_symptoms')
