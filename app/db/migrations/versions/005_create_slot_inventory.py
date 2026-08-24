"""create slot_inventory table

Revision ID: 005
Revises: 004
"""
from alembic import op

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute("""
        CREATE TABLE slot_inventory (
            uuid            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            centre_uuid     UUID NOT NULL REFERENCES centre(uuid),
            slot_date       DATE NOT NULL,
            slot_datetime   TIMESTAMP NOT NULL,
            is_booked       BOOLEAN NOT NULL DEFAULT FALSE,
            UNIQUE (centre_uuid, slot_datetime)
        )
    """)
    op.execute("CREATE INDEX slot_inventory_centre_date_idx ON slot_inventory (centre_uuid, slot_date) WHERE is_booked = FALSE")

def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS slot_inventory_centre_date_idx")
    op.execute("DROP TABLE IF EXISTS slot_inventory")