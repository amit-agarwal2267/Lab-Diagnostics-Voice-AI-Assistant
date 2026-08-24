"""create report table

Revision ID: 007
Revises: 006
"""
from alembic import op

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute("""
        CREATE TABLE appointment_test (
            appointment_uuid    UUID NOT NULL REFERENCES appointment(uuid) ON DELETE CASCADE,
            lab_test_uuid       UUID NOT NULL REFERENCES lab_test(uuid),
            PRIMARY KEY (appointment_uuid, lab_test_uuid)
        )
    """)

def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS appointment_test")