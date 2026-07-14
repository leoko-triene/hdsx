"""Add knowledge point grading links and parent authorization."""
from alembic import op
import sqlalchemy as sa

revision = "0002_learning_family"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    question_columns = {column["name"] for column in inspector.get_columns("questions")}
    if "knowledge_point_ids_json" not in question_columns:
        op.add_column("questions", sa.Column("knowledge_point_ids_json", sa.JSON(), nullable=True))
    op.execute("UPDATE questions SET knowledge_point_ids_json = JSON_ARRAY() WHERE knowledge_point_ids_json IS NULL")
    op.alter_column("questions", "knowledge_point_ids_json", existing_type=sa.JSON(), nullable=False)
    if "parent_student_links" not in inspector.get_table_names():
        op.create_table(
            "parent_student_links",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("parent_id", sa.BigInteger(), nullable=False),
            sa.Column("student_id", sa.BigInteger(), nullable=False),
            sa.Column("status", sa.String(30), nullable=False, server_default="active"),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["parent_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["student_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("parent_id", "student_id"),
        )
        op.create_index("ix_parent_student_links_parent_id", "parent_student_links", ["parent_id"])
        op.create_index("ix_parent_student_links_student_id", "parent_student_links", ["student_id"])


def downgrade():
    op.drop_table("parent_student_links")
    op.drop_column("questions", "knowledge_point_ids_json")
