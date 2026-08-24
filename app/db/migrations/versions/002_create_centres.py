"""create patient table

Revision ID: 002
Revises: 001
"""
from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute("""
        CREATE TABLE centre (
            uuid                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name                    TEXT NOT NULL,
            code                    TEXT NOT NULL UNIQUE,
            address                 TEXT NOT NULL,
            phone_number            TEXT,
            email                   TEXT,
            pincode                 TEXT NOT NULL,
            city                    TEXT NOT NULL,
            district                TEXT,
            state                   TEXT NOT NULL,
            country                 TEXT NOT NULL DEFAULT 'India',
            map_location            TEXT,                          
            supports_home_visit     BOOLEAN NOT NULL DEFAULT TRUE,
            supports_visit_center   BOOLEAN NOT NULL DEFAULT TRUE,
            is_active               BOOLEAN NOT NULL DEFAULT TRUE,
            created_at              TIMESTAMP NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX centre_city_active_idx ON centre (city) WHERE is_active = TRUE")
    op.execute("CREATE INDEX centre_pincode_active_idx ON centre (pincode) WHERE is_active = TRUE")

def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS centre_pincode_active_idx")
    op.execute("DROP INDEX IF EXISTS centre_city_active_idx")
    op.execute("DROP TABLE IF EXISTS centre")