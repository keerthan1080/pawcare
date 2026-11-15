"""add oauth_identities and mobile_otp_challenges tables

Revision ID: 0006_multi_provider_auth
Revises: 0005_admin_whatsapp_workflow
Create Date: 2026-11-15 13:15:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "0006_multi_provider_auth"
down_revision = "0005_admin_whatsapp_workflow"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "oauth_identities",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(length=24), nullable=False),  # GOOGLE | OKTA
        sa.Column("provider_subject", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("provider", "provider_subject", name="uq_oauth_provider_subject"),
    )
    op.create_index("ix_oauth_identities_user_id", "oauth_identities", ["user_id"], unique=False)

    op.create_table(
        "mobile_otp_challenges",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("phone", sa.String(length=30), nullable=False),
        sa.Column("otp_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False, server_default="PET_PARENT"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_consumed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("expires_at", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_mobile_otp_challenges_phone", "mobile_otp_challenges", ["phone"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_mobile_otp_challenges_phone", table_name="mobile_otp_challenges")
    op.drop_table("mobile_otp_challenges")
    op.drop_index("ix_oauth_identities_user_id", table_name="oauth_identities")
    op.drop_table("oauth_identities")
