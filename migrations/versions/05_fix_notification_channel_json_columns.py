"""Fix notification_channels text columns to json type

Revision ID: 05_fix_notification_channel_json_columns
Revises: 04_fix_notification_channel_enabled_type
Create Date: 2026-03-21 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "05_fix_notification_channel_json_columns"
down_revision = "04_fix_notification_channel_enabled_type"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "notification_channels",
        "days_in_advance",
        existing_type=sa.Text(),
        type_=sa.JSON(),
        existing_nullable=False,
        postgresql_using="days_in_advance::json",
    )
    op.alter_column(
        "notification_channels",
        "notification_data",
        existing_type=sa.Text(),
        type_=sa.JSON(),
        existing_nullable=True,
        postgresql_using="notification_data::json",
    )


def downgrade():
    op.alter_column(
        "notification_channels",
        "notification_data",
        existing_type=sa.JSON(),
        type_=sa.Text(),
        existing_nullable=True,
        postgresql_using="notification_data::text",
    )
    op.alter_column(
        "notification_channels",
        "days_in_advance",
        existing_type=sa.JSON(),
        type_=sa.Text(),
        existing_nullable=False,
        postgresql_using="days_in_advance::text",
    )
