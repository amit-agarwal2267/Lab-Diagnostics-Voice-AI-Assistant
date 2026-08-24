"""create ticket table

Revision ID: 010
Revises: 009
"""
from alembic import op

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute("""
        CREATE TABLE ticket (
            uuid            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            patient_uuid    UUID REFERENCES patient(uuid),
            category        TEXT NOT NULL CHECK (category IN ('email_correction', 'general')),
            description     TEXT,
            status          TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'resolved', 'escalated')),
            created_at      TIMESTAMP NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX ticket_open_idx ON ticket (status) WHERE status = 'open'")

def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ticket_open_idx")
    op.execute("DROP TABLE IF EXISTS ticket")