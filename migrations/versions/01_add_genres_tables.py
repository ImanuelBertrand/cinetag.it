"""Add TMDb genres tables and movie_genres association

Revision ID: 01_add_genres_tables
Revises: 00_create_initial_tables
Create Date: 2025-11-04 20:40:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "01_add_genres_tables"
down_revision = "00_create_initial_tables"
branch_labels = None
depends_on = None


def upgrade():
    # Create tmdb_genres table
    op.create_table(
        "tmdb_genres",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create tmdb_genre_names table
    op.create_table(
        "tmdb_genre_names",
        sa.Column("genre_id", sa.Integer(), nullable=False),
        sa.Column("language", sa.String(length=8), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["genre_id"],
            ["tmdb_genres.id"],
        ),
        sa.PrimaryKeyConstraint("genre_id", "language"),
    )
    op.create_index(
        "ix_tmdb_genre_names_language_name",
        "tmdb_genre_names",
        ["language", "name"],
    )

    # Create movie_genres association table
    op.create_table(
        "movie_genres",
        sa.Column("movie_id", sa.Integer(), nullable=False),
        sa.Column("genre_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["movie_id"],
            ["movies.id"],
        ),
        sa.ForeignKeyConstraint(
            ["genre_id"],
            ["tmdb_genres.id"],
        ),
        sa.PrimaryKeyConstraint("movie_id", "genre_id"),
    )


def downgrade():
    op.drop_table("movie_genres")
    op.drop_index("ix_tmdb_genre_names_language_name", table_name="tmdb_genre_names")
    op.drop_table("tmdb_genre_names")
    op.drop_table("tmdb_genres")
