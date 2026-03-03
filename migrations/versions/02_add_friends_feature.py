"""Add friends feature

Revision ID: 02_add_friends_feature
Revises: 01_add_genres_tables
Create Date: 2025-05-29 15:10:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.sql import func

# revision identifiers, used by Alembic.
revision = "02_add_friends_feature"
down_revision = "01_add_genres_tables"
branch_labels = None
depends_on = None


def upgrade():
    # 1. Add new columns to users table
    op.alter_column("users", "name", new_column_name="display_name")
    op.add_column(
        "users",
        sa.Column("friend_code", sa.String(64), nullable=True, unique=True),
    )

    # 2. Create friend_requests table
    op.create_table(
        "friend_requests",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("requester_id", sa.Integer(), nullable=False),
        sa.Column("recipient_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=func.now(),
            onupdate=func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["requester_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recipient_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("requester_id", "recipient_id", name="friend_request_idx"),
    )

    # 3. Create friendships table
    op.create_table(
        "friendships",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("user1_id", sa.Integer(), nullable=False),
        sa.Column("user2_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=func.now(),
            onupdate=func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user1_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user2_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user1_id", "user2_id", name="friendship_idx"),
        sa.CheckConstraint("user1_id < user2_id", name="check_user_order"),
    )

    # 4. Generate friend codes for existing users with email addresses
    # This is done in Python code rather than SQL for better compatibility
    conn = op.get_bind()

    # Get all users with email addresses but no friend code
    users = conn.execute(
        sa.text("SELECT id FROM users WHERE email IS NOT NULL AND friend_code IS NULL")
    ).fetchall()

    # Generate a simple friend code for each user
    for user in users:
        user_id = user[0]
        # Generate a simple friend code based on user ID and a random string
        random_string = conn.execute(
            sa.text("SELECT SUBSTRING(MD5(RAND()), 1, 8)")
        ).scalar()
        friend_code = f"user-{user_id}-{random_string}"
        conn.execute(
            sa.text("UPDATE users SET friend_code = :friend_code WHERE id = :user_id"),
            {"friend_code": friend_code, "id": int(user_id)},
        )


def downgrade():
    # Drop the tables and columns in reverse order
    op.drop_table("friendships")
    op.drop_table("friend_requests")
    op.drop_column("users", "friend_code")
    op.drop_column("users", "display_name")
