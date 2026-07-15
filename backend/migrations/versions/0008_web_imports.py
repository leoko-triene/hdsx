"""Add confirmed web source imports for the course knowledge base."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = "0008_web_imports"
down_revision = "0007_classroom_ops"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("documents")}
    if "source_url" not in columns:
        op.add_column("documents", sa.Column("source_url", sa.String(2000), nullable=True))
    tables = inspector.get_table_names()
    if "web_import_drafts" not in tables:
        op.create_table(
            "web_import_drafts",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("course_id", sa.BigInteger(), nullable=False),
            sa.Column("creator_id", sa.BigInteger(), nullable=False),
            sa.Column("source_url", sa.String(2000), nullable=False),
            sa.Column("resolved_url", sa.String(2000), nullable=False),
            sa.Column("source_domain", sa.String(255), nullable=False),
            sa.Column("title", sa.String(500), nullable=False),
            sa.Column("content", mysql.MEDIUMTEXT(), nullable=False),
            sa.Column("content_hash", sa.String(64), nullable=False),
            sa.Column("status", sa.String(30), server_default="pending", nullable=False),
            sa.Column("fetched_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("confirmed_document_id", sa.BigInteger(), nullable=True),
            sa.Column("metadata_json", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["course_id"], ["courses.id"]),
            sa.ForeignKeyConstraint(["creator_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["confirmed_document_id"], ["documents.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_web_import_drafts_course_id", "web_import_drafts", ["course_id"])
        op.create_index("ix_web_import_drafts_creator_id", "web_import_drafts", ["creator_id"])
        op.create_index("ix_web_import_drafts_source_domain", "web_import_drafts", ["source_domain"])
        op.create_index("ix_web_import_drafts_content_hash", "web_import_drafts", ["content_hash"])
        op.create_index("ix_web_import_drafts_status", "web_import_drafts", ["status"])
        op.create_index("ix_web_import_drafts_expires_at", "web_import_drafts", ["expires_at"])


def downgrade():
    op.drop_table("web_import_drafts")
    op.drop_column("documents", "source_url")
