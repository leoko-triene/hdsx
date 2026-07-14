"""Add generated documents export."""
from alembic import op
import sqlalchemy as sa

revision = "0008_generated_documents"
down_revision = "0007_classroom_ops"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "generated_documents",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("course_id", sa.BigInteger(), nullable=False),
        sa.Column("chapter_id", sa.BigInteger(), nullable=True),
        sa.Column("creator_id", sa.BigInteger(), nullable=False),
        sa.Column("source_resource_id", sa.BigInteger(), nullable=False),
        sa.Column("doc_type", sa.String(20), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("storage_path", sa.String(1000), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "draft", "processing", "ready", "published",
                "pending_review", "approved", "failed", "archived",
                name="status",
            ),
            nullable=False,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["chapter_id"], ["chapters.id"]),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"]),
        sa.ForeignKeyConstraint(["creator_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["source_resource_id"], ["lesson_resources.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_generated_documents_course_id", "generated_documents", ["course_id"])
    op.create_index("ix_generated_documents_creator_id", "generated_documents", ["creator_id"])
    op.create_index("ix_generated_documents_source_resource_id", "generated_documents", ["source_resource_id"])


def downgrade():
    op.drop_index("ix_generated_documents_source_resource_id", table_name="generated_documents")
    op.drop_index("ix_generated_documents_creator_id", table_name="generated_documents")
    op.drop_index("ix_generated_documents_course_id", table_name="generated_documents")
    op.drop_table("generated_documents")
