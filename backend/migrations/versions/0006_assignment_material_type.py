"""Classify generated assignment teaching materials."""
from alembic import op
import sqlalchemy as sa

revision = "0006_assignment_material"
down_revision = "0005_lesson_history"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("questions")}
    if "material_type" not in columns:
        op.add_column("questions", sa.Column("material_type", sa.String(30), nullable=False, server_default="exercise"))
    indexes = inspector.get_indexes("questions")
    if not any(item["name"] == "ix_questions_material_type" for item in indexes):
        op.create_index("ix_questions_material_type", "questions", ["material_type"])


def downgrade():
    op.drop_index("ix_questions_material_type", table_name="questions")
    op.drop_column("questions", "material_type")
