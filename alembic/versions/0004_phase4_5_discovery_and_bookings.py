"""phase 4 & 5 bookings and booking_items tables

Revision ID: 0004_phase5_bookings
Revises: 0003_phase3_caregivers
Create Date: 2026-11-14 13:04:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_phase5_bookings"
down_revision = "0003_phase3_caregivers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bookings",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("pet_parent_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("caregiver_id", sa.String(length=36), sa.ForeignKey("caregivers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("pet_id", sa.String(length=36), sa.ForeignKey("pets.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("availability_slot_id", sa.String(length=36), sa.ForeignKey("availability.id", ondelete="SET NULL"), nullable=True),
        sa.Column("service_type", sa.String(length=40), sa.ForeignKey("services.code", ondelete="RESTRICT"), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="PAYMENT_PENDING"),
        sa.Column("unit_price_inr", sa.Float(), nullable=False),
        sa.Column("price_unit", sa.String(length=30), nullable=False),
        sa.Column("units_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("subtotal_inr", sa.Float(), nullable=False),
        sa.Column("platform_commission_inr", sa.Float(), nullable=False),
        sa.Column("caregiver_payout_inr", sa.Float(), nullable=False),
        sa.Column("total_price_inr", sa.Float(), nullable=False),
        sa.Column("special_instructions", sa.Text(), nullable=True),
        sa.Column("cancellation_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_bookings_pet_parent_id", "bookings", ["pet_parent_id"], unique=False)
    op.create_index("ix_bookings_caregiver_id", "bookings", ["caregiver_id"], unique=False)
    op.create_index("ix_bookings_pet_id", "bookings", ["pet_id"], unique=False)
    op.create_index("ix_bookings_status", "bookings", ["status"], unique=False)
    op.create_index("ix_bookings_time_window", "bookings", ["caregiver_id", "start_time", "end_time"], unique=False)

    op.create_table(
        "booking_items",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("booking_id", sa.String(length=36), sa.ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("item_type", sa.String(length=40), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("unit_amount_inr", sa.Float(), nullable=False),
        sa.Column("total_amount_inr", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_booking_items_booking_id", "booking_items", ["booking_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_booking_items_booking_id", table_name="booking_items")
    op.drop_table("booking_items")
    op.drop_index("ix_bookings_time_window", table_name="bookings")
    op.drop_index("ix_bookings_status", table_name="bookings")
    op.drop_index("ix_bookings_pet_id", table_name="bookings")
    op.drop_index("ix_bookings_caregiver_id", table_name="bookings")
    op.drop_index("ix_bookings_pet_parent_id", table_name="bookings")
    op.drop_table("bookings")
