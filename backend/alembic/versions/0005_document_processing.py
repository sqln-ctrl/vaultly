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

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("document_id", sa.Uuid(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_chat_messages_document_id", "chat_messages", ["document_id"])
    op.create_index("ix_chat_messages_user_id", "chat_messages", ["user_id"])


def downgrade():
    op.drop_index("ix_chat_messages_user_id", "chat_messages")
    op.drop_index("ix_chat_messages_document_id", "chat_messages")
    op.drop_table("chat_messages")
    with op.batch_alter_table("documents") as batch_op:
        batch_op.drop_column("extracted_text")
