"""add document processing text and chat messages

Revision ID: 0005
Revises: 0004
"""
import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("documents") as batch_op:
        batch_op.add_column(sa.Column("extracted_text", sa.Text(), nullable=True))

def downgrade():
    with op.batch_alter_table("documents") as batch_op:
        batch_op.drop_column("extracted_text")
