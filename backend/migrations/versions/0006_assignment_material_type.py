"""Classify generated assignment teaching materials."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0006_assignment_material"
down_revision = "0005_lesson_history"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    return column in {c["name"] for c in inspect(op.get_bind()).get_columns(table)}


def _index_exists(table: str, name: str) -> bool:
    return name in {idx["name"] for idx in inspect(op.get_bind()).get_indexes(table)}


def upgrade():
    if not _has_column("questions", "material_type"):
        op.add_column("questions", sa.Column("material_type", sa.String(30), nullable=False, server_default="exercise"))
    if not _index_exists("questions", "ix_questions_material_type"):
        op.create_index("ix_questions_material_type", "questions", ["material_type"])


def downgrade():
    if _index_exists("questions", "ix_questions_material_type"):
        op.drop_index("ix_questions_material_type", table_name="questions")
    if _has_column("questions", "material_type"):
        op.drop_column("questions", "material_type")
