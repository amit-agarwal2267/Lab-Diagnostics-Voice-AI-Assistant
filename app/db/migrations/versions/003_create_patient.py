"""create patient table

Revision ID: 003
Revises: 002
"""
from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute("""
        CREATE TABLE patient (
            uuid            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name            TEXT NOT NULL,
            age             INT NOT NULL,
            phone_number    TEXT,
            email_address   TEXT UNIQUE,
            address         TEXT,
            created_at      TIMESTAMP NOT NULL DEFAULT now()
        )
    """)

def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS patient")