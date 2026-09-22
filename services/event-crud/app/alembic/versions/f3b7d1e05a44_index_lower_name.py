"""Index lowercased venue and performer names

Revision ID: f3b7d1e05a44
Revises: e7c1a4b82f30
Create Date: 2026-09-22 17:32:00.000000

"""

from alembic import op

revision = "f3b7d1e05a44"
down_revision = "e7c1a4b82f30"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX ix_venue_lower_name ON venue (lower(name) text_pattern_ops)"
    )
    op.execute(
        "CREATE INDEX ix_performer_lower_name "
        "ON performer (lower(name) text_pattern_ops)"
    )


def downgrade() -> None:
    op.drop_index("ix_performer_lower_name", table_name="performer")
    op.drop_index("ix_venue_lower_name", table_name="venue")
