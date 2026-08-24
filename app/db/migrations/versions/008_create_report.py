"""create report table

Revision ID: 008
Revises: 007
"""
from alembic import op

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute("""
        CREATE TABLE report (
            uuid                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            patient_uuid         UUID NOT NULL REFERENCES patient(uuid),
            appointment_uuid     UUID REFERENCES appointment(uuid),
            centre_uuid          UUID NOT NULL REFERENCES centre(uuid),
            sample_given_date    DATE,
            generation_date      DATE,
            status               TEXT NOT NULL CHECK (status IN ('in_progress', 'ready')),
            storage_path         TEXT,
            last_resent_at       TIMESTAMP,
            last_resent_channel  TEXT,
            deleted_at           TIMESTAMP
        )
    """)
    op.execute("CREATE INDEX report_patient_idx ON report (patient_uuid)")
    op.execute("CREATE INDEX report_centre_idx  ON report (centre_uuid)")
    op.execute("CREATE INDEX report_generation_date_idx ON report (generation_date)")

def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS report_generation_date_idx")
    op.execute("DROP INDEX IF EXISTS report_centre_idx")
    op.execute("DROP INDEX IF EXISTS report_patient_idx")
    op.execute("DROP TABLE IF EXISTS report")