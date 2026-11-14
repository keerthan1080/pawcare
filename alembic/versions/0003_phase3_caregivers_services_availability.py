"""phase 3 caregivers, services, caregiver_services, caregiver_verifications, and availability

Revision ID: 0003_phase3_caregivers
Revises: 0002_phase2_pets
Create Date: 2026-11-14 12:37:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_phase3_caregivers"
down_revision = "0002_phase2_pets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "services",
        sa.Column("code", sa.String(length=40), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("default_price_unit", sa.String(length=30), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )

    op.create_table(
        "caregivers",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("bio", sa.Text(), nullable=False),
        sa.Column("years_of_experience", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("experience_summary", sa.Text(), nullable=True),
        sa.Column("profile_photo_url", sa.String(length=512), nullable=True),
        sa.Column("city", sa.String(length=80), nullable=False),
        sa.Column("locality", sa.String(length=120), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("service_radius_km", sa.Float(), nullable=False, server_default="5.0"),
        sa.Column("supported_species_json", sa.Text(), nullable=False),
        sa.Column("max_pet_weight_kg", sa.Float(), nullable=True),
        sa.Column("special_capabilities_json", sa.Text(), nullable=False),
        sa.Column("boarding_details_json", sa.Text(), nullable=True),
        sa.Column("verification_status", sa.String(length=32), nullable=False, server_default="PENDING"),
        sa.Column("rating_average", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("review_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_caregivers_user_id", "caregivers", ["user_id"], unique=True)
    op.create_index("ix_caregivers_city", "caregivers", ["city"], unique=False)
    op.create_index("ix_caregivers_verification_status", "caregivers", ["verification_status"], unique=False)

    op.create_table(
        "caregiver_services",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("caregiver_id", sa.String(length=36), sa.ForeignKey("caregivers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("service_type", sa.String(length=40), sa.ForeignKey("services.code", ondelete="RESTRICT"), nullable=False),
        sa.Column("price_inr", sa.Float(), nullable=False),
        sa.Column("price_unit", sa.String(length=30), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("caregiver_id", "service_type", name="uq_caregiver_service_type"),
    )
    op.create_index("ix_caregiver_services_caregiver_id", "caregiver_services", ["caregiver_id"], unique=False)
    op.create_index("ix_caregiver_services_service_type", "caregiver_services", ["service_type"], unique=False)

    op.create_table(
        "caregiver_verifications",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("caregiver_id", sa.String(length=36), sa.ForeignKey("caregivers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("document_reference", sa.String(length=512), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="PENDING"),
        sa.Column("reviewed_by_user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_caregiver_verifications_caregiver_id", "caregiver_verifications", ["caregiver_id"], unique=False)

    op.create_table(
        "availability",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("caregiver_id", sa.String(length=36), sa.ForeignKey("caregivers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("max_capacity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("booked_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_available", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("notes", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_availability_caregiver_id", "availability", ["caregiver_id"], unique=False)
    op.create_index("ix_availability_window", "availability", ["caregiver_id", "start_time", "end_time"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_availability_window", table_name="availability")
    op.drop_index("ix_availability_caregiver_id", table_name="availability")
    op.drop_table("availability")
    op.drop_index("ix_caregiver_verifications_caregiver_id", table_name="caregiver_verifications")
    op.drop_table("caregiver_verifications")
    op.drop_index("ix_caregiver_services_service_type", table_name="caregiver_services")
    op.drop_index("ix_caregiver_services_caregiver_id", table_name="caregiver_services")
    op.drop_table("caregiver_services")
    op.drop_index("ix_caregivers_verification_status", table_name="caregivers")
    op.drop_index("ix_caregivers_city", table_name="caregivers")
    op.drop_index("ix_caregivers_user_id", table_name="caregivers")
    op.drop_table("caregivers")
    op.drop_table("services")
