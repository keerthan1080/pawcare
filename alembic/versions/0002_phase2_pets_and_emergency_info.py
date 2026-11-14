"""phase 2 pets, emergency_contacts, veterinarians, and pet_medical_records

Revision ID: 0002_phase2_pets
Revises: 0001_foundation
Create Date: 2026-11-14 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_phase2_pets"
down_revision = "0001_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pets",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("owner_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("species", sa.String(length=32), nullable=False),
        sa.Column("breed", sa.String(length=100), nullable=True),
        sa.Column("gender", sa.String(length=20), nullable=False, server_default="UNKNOWN"),
        sa.Column("date_of_birth", sa.String(length=10), nullable=True),
        sa.Column("age_years", sa.Float(), nullable=True),
        sa.Column("weight_kg", sa.Float(), nullable=True),
        sa.Column("photo_url", sa.String(length=512), nullable=True),
        sa.Column("personality", sa.Text(), nullable=True),
        sa.Column("feeding_instructions", sa.Text(), nullable=True),
        sa.Column("feeding_schedule_json", sa.Text(), nullable=True),
        sa.Column("walking_schedule_json", sa.Text(), nullable=True),
        sa.Column("medication_instructions", sa.Text(), nullable=True),
        sa.Column("allergies", sa.Text(), nullable=True),
        sa.Column("behaviour_notes", sa.Text(), nullable=True),
        sa.Column("special_requirements", sa.Text(), nullable=True),
        sa.Column("additional_notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_pets_owner_id", "pets", ["owner_id"], unique=False)
    op.create_index("ix_pets_species", "pets", ["species"], unique=False)

    op.create_table(
        "emergency_contacts",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("pet_id", sa.String(length=36), sa.ForeignKey("pets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("relationship", sa.String(length=64), nullable=False),
        sa.Column("phone", sa.String(length=30), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_emergency_contacts_pet_id", "emergency_contacts", ["pet_id"], unique=False)

    op.create_table(
        "veterinarians",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("pet_id", sa.String(length=36), sa.ForeignKey("pets.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("clinic_name", sa.String(length=150), nullable=False),
        sa.Column("vet_name", sa.String(length=120), nullable=True),
        sa.Column("phone", sa.String(length=30), nullable=False),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_veterinarians_pet_id", "veterinarians", ["pet_id"], unique=True)

    op.create_table(
        "pet_medical_records",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("pet_id", sa.String(length=36), sa.ForeignKey("pets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("record_type", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=150), nullable=False),
        sa.Column("administered_date", sa.String(length=10), nullable=True),
        sa.Column("expiry_date", sa.String(length=10), nullable=True),
        sa.Column("provider_name", sa.String(length=150), nullable=True),
        sa.Column("document_url", sa.String(length=512), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_pet_medical_records_pet_id", "pet_medical_records", ["pet_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_pet_medical_records_pet_id", table_name="pet_medical_records")
    op.drop_table("pet_medical_records")
    op.drop_index("ix_veterinarians_pet_id", table_name="veterinarians")
    op.drop_table("veterinarians")
    op.drop_index("ix_emergency_contacts_pet_id", table_name="emergency_contacts")
    op.drop_table("emergency_contacts")
    op.drop_index("ix_pets_species", table_name="pets")
    op.drop_index("ix_pets_owner_id", table_name="pets")
    op.drop_table("pets")
