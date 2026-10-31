"""remove obsolete per-document chat table

Revision ID: 0007
Revises: 0006
"""
import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if "chat_messages" in inspector.get_table_names():
        index_names = {index["name"] for index in inspector.get_indexes("chat_messages")}
        if "ix_chat_messages_user_id" in index_names:
            op.drop_index("ix_chat_messages_user_id", "chat_messages")
        if "ix_chat_messages_document_id" in index_names:
            op.drop_index("ix_chat_messages_document_id", "chat_messages")
        op.drop_table("chat_messages")


def downgrade():
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("document_id", sa.Uuid(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
