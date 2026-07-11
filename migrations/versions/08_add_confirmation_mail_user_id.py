"""Add user_id to sent_confirmation_mails for per-account rate limiting

Revision ID: 08_add_confirmation_mail_user_id
Revises: 07_add_credits_tables
Create Date: 2026-07-11 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "08_add_confirmation_mail_user_id"
down_revision = "07_add_credits_tables"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "sent_confirmation_mails",
        sa.Column("user_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        op.f("ix_sent_confirmation_mails_user_id"),
        "sent_confirmation_mails",
        ["user_id"],
    )
    op.create_foreign_key(
        "fk_sent_confirmation_mails_user_id_users",
        "sent_confirmation_mails",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade():
    op.drop_constraint(
        "fk_sent_confirmation_mails_user_id_users",
        "sent_confirmation_mails",
        type_="foreignkey",
    )
    op.drop_index(
        op.f("ix_sent_confirmation_mails_user_id"),
        table_name="sent_confirmation_mails",
    )
    op.drop_column("sent_confirmation_mails", "user_id")
