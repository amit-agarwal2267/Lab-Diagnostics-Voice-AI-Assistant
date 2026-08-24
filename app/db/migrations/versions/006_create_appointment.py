"""create appointment table

Revision ID: 006
Revises: 005
"""
from alembic import op

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute("""
        CREATE TABLE appointment (
            uuid                        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            patient_uuid                UUID NOT NULL REFERENCES patient(uuid),
            centre_uuid                 UUID NOT NULL REFERENCES centre(uuid),
            slot_datetime               TIMESTAMP NOT NULL,
            requires_prescription       BOOLEAN NOT NULL DEFAULT FALSE,
            status                      TEXT NOT NULL CHECK (status IN (
                                            'pending_confirmation',
                                            'awaiting_payment',
                                            'confirmed'
                                        )),
            payment_link                TEXT,
            mode_of_sample_collection   TEXT NOT NULL CHECK (mode_of_sample_collection IN (
                                            'Visit Center',
                                            'Home Visit'
                                        )),
            mode_of_payment             TEXT CHECK (mode_of_payment IN (
                                            'UPI',
                                            'Cash on Visit'
                                        )),
            created_at                  TIMESTAMP NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX appointment_patient_idx ON appointment (patient_uuid)")
    op.execute("CREATE INDEX appointment_centre_idx  ON appointment (centre_uuid)")

def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS appointment_centre_idx")
    op.execute("DROP INDEX IF EXISTS appointment_patient_idx")
    op.execute("DROP TABLE IF EXISTS appointment")