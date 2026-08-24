"""create lab_test table

Revision ID: 004
Revises: 003
"""
from alembic import op

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute("""
        CREATE TABLE lab_test (
            uuid                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            test_name               TEXT NOT NULL UNIQUE,
            price                   NUMERIC(10, 2) NOT NULL,
            requires_prescription   BOOLEAN NOT NULL DEFAULT FALSE,
            pre_test_instructions   TEXT
        )
    """)

def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS lab_test")