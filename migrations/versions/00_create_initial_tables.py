"""Create initial tables

Revision ID: 00_create_initial_tables
Revises:
Create Date: 2025-05-29 14:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "00_create_initial_tables"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create users table
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(200), nullable=True),
        sa.Column("email", sa.String(120), unique=True, nullable=True),
        sa.Column("new_email", sa.String(120), unique=True, nullable=True),
        sa.Column("password", sa.String(128), nullable=True),
        sa.Column("region", sa.String(2), nullable=True, server_default="US"),
        sa.Column("language", sa.String(5), nullable=True, server_default="en"),
        sa.Column("temporary_user_id", sa.Integer(), nullable=True),
        sa.Column("password_reset_token", sa.String(32), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create movies table
    op.create_table(
        "movies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("original_title", sa.String(255), nullable=False),
        sa.Column("popularity", sa.Float(), nullable=True),
        sa.Column("original_language", sa.String(2), nullable=True),
        sa.Column("info_update_at", sa.DateTime(), nullable=True),
        sa.Column("imdb_id", sa.String(20), nullable=True),
        sa.Column("origin_country", sa.String(255), nullable=True),
        sa.Column("runtime", sa.Integer(), nullable=True),
        sa.Column("spoken_languages", sa.String(255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create user_movies table
    op.create_table(
        "user_movies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("movie_id", sa.Integer(), nullable=False),
        sa.Column("decision", sa.String(10), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["movie_id"],
            ["movies.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "movie_id", name="user_movie_idx"),
    )

    # Create user_calendars table
    op.create_table(
        "user_calendars",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("calendar_type", sa.String(10), nullable=False),
        sa.Column("calendar_hash", sa.String(64), nullable=False, unique=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "calendar_type", name="user_calendar_idx"),
    )

    # Create notification_channels table
    op.create_table(
        "notification_channels",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Integer(), nullable=True),
        sa.Column("days_in_advance", sa.JSON(), nullable=False),
        sa.Column("mode", sa.Enum("email", "push"), nullable=False),
        sa.Column("notification_data", sa.JSON(), nullable=True),
        sa.Column(
            "include_maybe_movies",
            sa.Boolean(),
            nullable=True,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create notifications table
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("channel_id", sa.Integer(), nullable=False),
        sa.Column("movie_id", sa.Integer(), nullable=False),
        sa.Column("days_in_advance", sa.Integer(), nullable=False),
        sa.Column("is_sent", sa.Boolean(), nullable=True, server_default=sa.text("0")),
        sa.Column("scheduled_at", sa.DateTime(), nullable=True),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["channel_id"],
            ["notification_channels.id"],
        ),
        sa.ForeignKeyConstraint(
            ["movie_id"],
            ["movies.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create movie_region_info table
    op.create_table(
        "movie_region_info",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("movie_id", sa.Integer(), nullable=False),
        sa.Column("region", sa.String(2), nullable=False),
        sa.Column("release_date", sa.Date(), nullable=False),
        sa.Column("is_fake", sa.Boolean(), nullable=True, server_default=sa.text("0")),
        sa.ForeignKeyConstraint(
            ["movie_id"],
            ["movies.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("movie_id", "region", name="movie_region_info_idx"),
    )
    op.create_index(
        "movie_region_info_release_date_idx", "movie_region_info", ["release_date"]
    )

    # Create movie_language_info table
    op.create_table(
        "movie_language_info",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("movie_id", sa.Integer(), nullable=False),
        sa.Column("language", sa.String(5), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("poster_path", sa.String(255), nullable=True),
        sa.Column("overview", sa.Text(), nullable=True),
        sa.Column("tagline", sa.String(255), nullable=True),
        sa.Column("runtime", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["movie_id"],
            ["movies.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("movie_id", "language", name="movie_language_info_idx"),
    )

    # Create allowed_refresh_tokens table
    op.create_table(
        "allowed_refresh_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("jti", sa.String(36), nullable=False, unique=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_allowed_refresh_tokens_jti", "allowed_refresh_tokens", ["jti"])
    op.create_index(
        "ix_allowed_refresh_tokens_user_id", "allowed_refresh_tokens", ["user_id"]
    )

    # Create misc_data table
    op.create_table(
        "misc_data",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(50), nullable=False, unique=True),
        sa.Column("value", sa.String(255), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create tmdb_languages table
    op.create_table(
        "tmdb_languages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(2), nullable=False, unique=True),
        sa.Column("english_name", sa.String(50), nullable=False),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column(
            "sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create tmdb_regions table
    op.create_table(
        "tmdb_regions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(2), nullable=False, unique=True),
        sa.Column("english_name", sa.String(50), nullable=False),
        sa.Column("native_name", sa.String(50), nullable=False),
        sa.Column(
            "sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create user_email_queue table
    op.create_table(
        "user_email_queue",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("mail_type", sa.String(10), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create sent_confirmation_mails table
    op.create_table(
        "sent_confirmation_mails",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(120), nullable=False),
        sa.Column(
            "sent_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade():
    # Drop tables in reverse order of creation
    # to avoid foreign key constraint violations
    op.drop_table("sent_confirmation_mails")
    op.drop_table("user_email_queue")
    op.drop_table("tmdb_regions")
    op.drop_table("tmdb_languages")
    op.drop_table("misc_data")
    op.drop_index(
        "ix_allowed_refresh_tokens_user_id", table_name="allowed_refresh_tokens"
    )
    op.drop_index("ix_allowed_refresh_tokens_jti", table_name="allowed_refresh_tokens")
    op.drop_table("allowed_refresh_tokens")
    op.drop_table("movie_language_info")
    op.drop_index("movie_region_info_release_date_idx", table_name="movie_region_info")
    op.drop_table("movie_region_info")
    op.drop_table("notifications")
    op.drop_table("notification_channels")
    op.drop_table("user_calendars")
    op.drop_table("user_movies")
    op.drop_table("movies")
    op.drop_table("users")
