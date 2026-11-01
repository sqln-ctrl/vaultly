"""add vault chat conversations

Revision ID: 0008
Revises: 0007
"""
import uuid

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    table_names = sa.inspect(bind).get_table_names()
    if "vault_chat_conversations" not in table_names:
        op.create_table(
            "vault_chat_conversations",
            sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
            sa.Column("user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("title", sa.String(120), nullable=False, server_default="New chat"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
    conversation_indexes = {index["name"] for index in sa.inspect(bind).get_indexes("vault_chat_conversations")}
    if "ix_vault_chat_conversations_user_id" not in conversation_indexes:
        op.create_index("ix_vault_chat_conversations_user_id", "vault_chat_conversations", ["user_id"])

    message_columns = {column["name"] for column in sa.inspect(bind).get_columns("vault_chat_messages")}
    if "conversation_id" not in message_columns:
        with op.batch_alter_table("vault_chat_messages") as batch_op:
            batch_op.add_column(sa.Column("conversation_id", sa.Uuid(as_uuid=True), nullable=True))
            batch_op.create_foreign_key(
                "fk_vault_chat_messages_conversation_id",
                "vault_chat_conversations",
                ["conversation_id"],
                ["id"],
                ondelete="CASCADE",
            )
            batch_op.create_index("ix_vault_chat_messages_conversation_id", ["conversation_id"])

    bind = op.get_bind()
    user_ids = bind.execute(sa.text(
        "SELECT DISTINCT user_id FROM vault_chat_messages WHERE conversation_id IS NULL"
    )).scalars()
    conversations = sa.table(
        "vault_chat_conversations",
        sa.column("id", sa.Uuid(as_uuid=True)),
        sa.column("user_id", sa.Uuid(as_uuid=True)),
        sa.column("title", sa.String()),
    )
    for user_id in user_ids:
        conversation_id = uuid.uuid4()
        user_id_value = uuid.UUID(str(user_id)) if not isinstance(user_id, uuid.UUID) else user_id
        bind.execute(conversations.insert().values(
            id=conversation_id,
            user_id=user_id_value,
            title="Previous chat",
        ))
        bind.execute(sa.text(
            "UPDATE vault_chat_messages SET conversation_id = :conversation_id "
            "WHERE user_id = :user_id AND conversation_id IS NULL"
        ).bindparams(conversation_id=conversation_id, user_id=user_id))


def downgrade():
    with op.batch_alter_table("vault_chat_messages") as batch_op:
        batch_op.drop_index("ix_vault_chat_messages_conversation_id")
        batch_op.drop_constraint("fk_vault_chat_messages_conversation_id", type_="foreignkey")
        batch_op.drop_column("conversation_id")
    op.drop_index("ix_vault_chat_conversations_user_id", "vault_chat_conversations")
    op.drop_table("vault_chat_conversations")
