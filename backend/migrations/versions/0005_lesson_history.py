"""Add persistent lesson resource history and save flag."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0005_lesson_history"
down_revision = "0004_course_membership"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    return column in {c["name"] for c in inspect(op.get_bind()).get_columns(table)}


def _index_exists(table: str, name: str) -> bool:
    return name in {idx["name"] for idx in inspect(op.get_bind()).get_indexes(table)}


def upgrade():
    if not _has_column("lesson_resources", "is_saved"):
        op.add_column("lesson_resources", sa.Column("is_saved", sa.Boolean(), nullable=False, server_default=sa.false()))
    if not _index_exists("lesson_resources", "ix_lesson_resources_is_saved"):
        op.create_index("ix_lesson_resources_is_saved", "lesson_resources", ["is_saved"])


def downgrade():
    if _index_exists("lesson_resources", "ix_lesson_resources_is_saved"):
        op.drop_index("ix_lesson_resources_is_saved", table_name="lesson_resources")
    if _has_column("lesson_resources", "is_saved"):
        op.drop_column("lesson_resources", "is_saved")
