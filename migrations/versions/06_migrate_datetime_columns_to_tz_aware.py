"""Migrate datetime columns to be TZ-aware

Revision ID: 06_migrate_datetime_columns_to_tz_aware
Revises: 05_fix_notification_channel_json_columns
Create Date: 2026-05-11 00:00:00.000000

The models were changed to use ``DateTime(timezone=True)`` in commit 7ed0240,
but the corresponding schema migration was never added. Existing values were
written by code that used ``datetime.utcnow()`` / ``datetime.now(UTC)``, and
the PostgreSQL session timezone is UTC, so naive stored values represent UTC
wall-clock time and can be reinterpreted as such.
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "06_migrate_datetime_columns_to_tz_aware"
down_revision = "05_fix_notification_channel_json_columns"
branch_labels = None
depends_on = None


COLUMNS = [
    ("friend_requests", "created_at", False),
    ("friend_requests", "updated_at", False),
    ("friendships", "created_at", False),
    ("friendships", "updated_at", False),
    ("movies", "info_update_at", True),
    ("notification_channels", "created_at", True),
    ("notification_channels", "updated_at", True),
    ("notifications", "created_at", True),
    ("notifications", "scheduled_at", True),
    ("notifications", "sent_at", True),
    ("notifications", "updated_at", True),
    ("sent_confirmation_mails", "sent_at", True),
    ("tmdb_genre_names", "updated_at", True),
    ("tmdb_genres", "updated_at", True),
    ("user_calendars", "created_at", True),
    ("user_calendars", "updated_at", True),
    ("user_movies", "created_at", True),
    ("user_movies", "updated_at", True),
    ("users", "created_at", True),
    ("users", "updated_at", True),
]


def upgrade():
    for table, column, nullable in COLUMNS:
        op.alter_column(
            table,
            column,
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=nullable,
            postgresql_using=f"{column} AT TIME ZONE 'UTC'",
        )


def downgrade():
    for table, column, nullable in COLUMNS:
        op.alter_column(
            table,
            column,
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=nullable,
            postgresql_using=f"{column} AT TIME ZONE 'UTC'",
        )
