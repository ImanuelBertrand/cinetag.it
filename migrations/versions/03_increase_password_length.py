"""Increase password column length

Revision ID: 03_increase_password_length
Revises: 02_add_friends_feature
Create Date: 2025-06-07 15:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "03_increase_password_length"
down_revision = "02_add_friends_feature"
branch_labels = None
depends_on = None


def upgrade():
    # Increase the password column length in the users table
    op.alter_column(
        "users",
        "password",
        existing_type=sa.String(128),
        type_=sa.String(255),
        existing_nullable=True,
    )


def downgrade():
    # Revert the password column length back to 128
    op.alter_column(
        "users",
        "password",
        existing_type=sa.String(255),
        type_=sa.String(128),
        existing_nullable=True,
    )
