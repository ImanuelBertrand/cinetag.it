"""Add people and movie_credits tables

Revision ID: 07_add_credits_tables
Revises: 06_migrate_datetime_columns_to_tz_aware
Create Date: 2026-05-12 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "07_add_credits_tables"
down_revision = "06_migrate_datetime_columns_to_tz_aware"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "people",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "movie_credits",
        sa.Column("movie_id", sa.Integer(), nullable=False),
        sa.Column("person_id", sa.Integer(), nullable=False),
        sa.Column("department", sa.String(length=8), nullable=False),
        sa.Column("role", sa.String(length=255), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["movie_id"], ["movies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["person_id"], ["people.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("movie_id", "person_id", "department", "role"),
    )
    op.create_index(
        "ix_movie_credits_movie_dept",
        "movie_credits",
        ["movie_id", "department"],
    )


def downgrade() -> None:
    op.drop_index("ix_movie_credits_movie_dept", table_name="movie_credits")
    op.drop_table("movie_credits")
    op.drop_table("people")
