"""Add race-safe document content deduplication key."""
from alembic import op
import sqlalchemy as sa

revision = "0003_document_dedup"
down_revision = "0002_learning_family"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("documents")}
    if "dedup_key" not in columns:
        op.add_column("documents", sa.Column("dedup_key", sa.String(64), nullable=True))
    constraints = inspector.get_unique_constraints("documents")
    if not any(item["name"] == "uq_documents_course_id_dedup_key" for item in constraints):
        op.create_unique_constraint("uq_documents_course_id_dedup_key", "documents", ["course_id", "dedup_key"])


def downgrade():
    op.drop_constraint("uq_documents_course_id_dedup_key", "documents", type_="unique")
    op.drop_column("documents", "dedup_key")
