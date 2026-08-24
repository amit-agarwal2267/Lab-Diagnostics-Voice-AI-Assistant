"""create report table

Revision ID: 009
Revises: 008
"""
from alembic import op

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute("""
        CREATE TABLE report_test (
            report_uuid     UUID NOT NULL REFERENCES report(uuid) ON DELETE CASCADE,
            lab_test_uuid   UUID NOT NULL REFERENCES lab_test(uuid),
            PRIMARY KEY (report_uuid, lab_test_uuid)
        )
    """)

def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS report_test")