"""Fix notification_channels.enabled column type from Integer to Boolean

Revision ID: 04_fix_notification_channel_enabled_type
Revises: 03_increase_password_length
Create Date: 2026-03-19 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "04_fix_notification_channel_enabled_type"
down_revision = "03_increase_password_length"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "notification_channels",
        "enabled",
        existing_type=sa.Integer(),
        type_=sa.Boolean(),
        existing_nullable=True,
        postgresql_using="enabled != 0",
    )


def downgrade():
    op.alter_column(
        "notification_channels",
        "enabled",
        existing_type=sa.Boolean(),
        type_=sa.Integer(),
        existing_nullable=True,
        postgresql_using="enabled::integer",
    )
