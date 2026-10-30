"""Add document and document field tables

Revision ID: 0003
Revises: 0002
"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("storage_key", sa.String(255), nullable=False, unique=True),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("page_count", sa.Integer()),
        sa.Column("category", sa.String(32), nullable=False, server_default="Other"),
        sa.Column("status", sa.String(16), nullable=False, server_default="uploaded"),
        sa.Column("error_message", sa.Text()),
        sa.Column("summary", sa.Text()),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_documents_user_id", "documents", ["user_id"])
    op.create_index("ix_documents_sha256", "documents", ["sha256"])
    op.create_table(
        "document_fields",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("document_id", sa.Uuid(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("vendor", sa.String(255)),
        sa.Column("doc_number", sa.String(255)),
        sa.Column("issue_date", sa.DateTime(timezone=True)),
        sa.Column("due_date", sa.DateTime(timezone=True)),
        sa.Column("expiry_date", sa.DateTime(timezone=True)),
        sa.Column("total_amount", sa.Numeric(12, 2)),
        sa.Column("tax_amount", sa.Numeric(12, 2)),
        sa.Column("currency", sa.String(3)),
        sa.Column("user_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_document_fields_document_id", "document_fields", ["document_id"], unique=True)


def downgrade():
    op.drop_index("ix_document_fields_document_id", "document_fields")
    op.drop_table("document_fields")
    op.drop_index("ix_documents_sha256", "documents")
    op.drop_index("ix_documents_user_id", "documents")
    op.drop_table("documents")
