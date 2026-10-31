"""add Google sign-in identity

Revision ID: 0004
Revises: 0003
"""
import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("password_hash", existing_type=sa.String(255), nullable=True)
        batch_op.add_column(sa.Column("google_sub", sa.String(255), nullable=True))
        batch_op.create_index("ix_users_google_sub", ["google_sub"], unique=True)


def downgrade():
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_index("ix_users_google_sub")
        batch_op.drop_column("google_sub")
        batch_op.alter_column("password_hash", existing_type=sa.String(255), nullable=False)
