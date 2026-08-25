"""create ticket table

Revision ID: 011
Revises: 010
"""
from alembic import op

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS fuzzystrmatch")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE INDEX patient_name_trgm_idx ON patient USING gin (name gin_trgm_ops)")
    op.execute("CREATE INDEX centre_city_trgm_idx ON centre USING gin (city gin_trgm_ops)")

def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS centre_city_trgm_idx")
    op.execute("DROP INDEX IF EXISTS patient_name_trgm_idx")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
    op.execute("DROP EXTENSION IF EXISTS fuzzystrmatch")