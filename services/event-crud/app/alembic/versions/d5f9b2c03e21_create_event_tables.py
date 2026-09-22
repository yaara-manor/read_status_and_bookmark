"""Create event tables

Revision ID: d5f9b2c03e21
Revises:
Create Date: 2026-09-22 11:15:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "d5f9b2c03e21"
down_revision = None
branch_labels = None
depends_on = None

performer_genre = postgresql.ENUM(
    "MUSIC",
    "SPORT",
    "THEATRE",
    "CIRCUS",
    name="performer_genre",
    create_type=False,
)
ticket_availability = postgresql.ENUM(
    "AVAILABLE",
    "BOOKED",
    name="ticket_availability",
    create_type=False,
)


def upgrade() -> None:
    performer_genre.create(op.get_bind(), checkfirst=True)
    ticket_availability.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "venue",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("city", sa.String(length=255), nullable=False),
        sa.Column("country", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("seat_map", postgresql.ARRAY(sa.Integer()), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "performer",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("genre", performer_genre, nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "event",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("venue_id", sa.Uuid(), nullable=False),
        sa.Column("performer_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("creator", sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(["venue_id"], ["venue.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["performer_id"], ["performer.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "ticket",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("row", sa.Integer(), nullable=False),
        sa.Column("seat", sa.Integer(), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("availability", ticket_availability, nullable=False),
        sa.CheckConstraint("price >= 0"),
        sa.CheckConstraint('"row" >= 0'),
        sa.CheckConstraint("seat >= 0"),
        sa.ForeignKeyConstraint(["event_id"], ["event.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", "row", "seat"),
    )
    op.create_table(
        "eventreadlink",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["event.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "event_id"),
    )
    op.create_table(
        "eventbookmarklink",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["event.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "event_id"),
    )


def downgrade() -> None:
    op.drop_table("eventbookmarklink")
    op.drop_table("eventreadlink")
    op.drop_table("ticket")
    op.drop_table("event")
    op.drop_table("performer")
    op.drop_table("venue")
    ticket_availability.drop(op.get_bind(), checkfirst=True)
    performer_genre.drop(op.get_bind(), checkfirst=True)
