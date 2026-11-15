"""add pet_media, notifications, and admin review columns on bookings

Revision ID: 0005_admin_whatsapp_workflow
Revises: 0004_phase5_bookings
Create Date: 2026-11-15 12:20:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "0005_admin_whatsapp_workflow"
down_revision = "0004_phase5_bookings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pet_media",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("pet_id", sa.String(length=36), sa.ForeignKey("pets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("media_type", sa.String(length=20), nullable=False),  # PHOTO | VIDEO
        sa.Column("title", sa.String(length=150), nullable=False),
        sa.Column("url", sa.String(length=512), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_pet_media_pet_id", "pet_media", ["pet_id"], unique=False)

    op.create_table(
        "notifications",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("booking_id", sa.String(length=36), sa.ForeignKey("bookings.id", ondelete="CASCADE"), nullable=True),
        sa.Column("recipient_role", sa.String(length=32), nullable=False),
        sa.Column("recipient_phone", sa.String(length=40), nullable=False),
        sa.Column("channel", sa.String(length=24), nullable=False, server_default="WHATSAPP"),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("message_body", sa.Text(), nullable=False),
        sa.Column("whatsapp_url", sa.Text(), nullable=False),
        sa.Column("delivery_status", sa.String(length=24), nullable=False, server_default="QUEUED"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_notifications_booking_id", "notifications", ["booking_id"], unique=False)

    op.add_column("bookings", sa.Column("media_reviewed_by_admin", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("bookings", sa.Column("admin_review_notes", sa.Text(), nullable=True))
    op.add_column("bookings", sa.Column("assigned_by_admin_id", sa.String(length=36), nullable=True))


def downgrade() -> None:
    op.drop_column("bookings", "assigned_by_admin_id")
    op.drop_column("bookings", "admin_review_notes")
    op.drop_column("bookings", "media_reviewed_by_admin")
    op.drop_index("ix_notifications_booking_id", table_name="notifications")
    op.drop_table("notifications")
    op.drop_index("ix_pet_media_pet_id", table_name="pet_media")
    op.drop_table("pet_media")
