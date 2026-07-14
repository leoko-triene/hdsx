"""Add race-safe document content deduplication key."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0003_document_dedup"
down_revision = "0002_learning_family"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    return column in {c["name"] for c in inspect(bind).get_columns(table)}


def _has_constraint(table: str, constraint: str) -> bool:
    bind = op.get_bind()
    return constraint in {c["name"] for c in inspect(bind).get_unique_constraints(table)}


def upgrade():
    if not _has_column("documents", "dedup_key"):
        op.add_column("documents", sa.Column("dedup_key", sa.String(64), nullable=True))
    if not _has_constraint("documents", "uq_documents_course_id_dedup_key"):
        op.create_unique_constraint("uq_documents_course_id_dedup_key", "documents", ["course_id", "dedup_key"])


def downgrade():
    if _has_constraint("documents", "uq_documents_course_id_dedup_key"):
        op.drop_constraint("uq_documents_course_id_dedup_key", "documents", type_="unique")
    if _has_column("documents", "dedup_key"):
        op.drop_column("documents", "dedup_key")
