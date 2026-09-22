"""Unique venue names

Revision ID: e7c1a4b82f30
Revises: d5f9b2c03e21
Create Date: 2026-09-22 14:40:00.000000

"""

from alembic import op

revision = "e7c1a4b82f30"
down_revision = "d5f9b2c03e21"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint("uq_venue_name", "venue", ["name"])


def downgrade() -> None:
    op.drop_constraint("uq_venue_name", "venue", type_="unique")
