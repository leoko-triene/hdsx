"""add knowledge point graph tables

Revision ID: 0010
Revises: 0009_submission_attempts
Create Date: 2025-01-01 00:00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = "0010"
down_revision = "0009_submission_attempts"
branch_labels = None
depends_on = None

def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = inspector.get_table_names()
    if "knowledge_point_relations" not in tables:
        op.create_table(
            "knowledge_point_relations",
            sa.Column("id", mysql.BIGINT(), autoincrement=True, nullable=False),
            sa.Column("course_id", mysql.BIGINT(), nullable=False),
            sa.Column("from_kp_id", mysql.BIGINT(), nullable=False),
            sa.Column("to_kp_id", mysql.BIGINT(), nullable=False),
            sa.Column("relation_type", sa.String(30), nullable=False, server_default="prerequisite"),
            sa.Column("confidence", mysql.FLOAT(), nullable=False, server_default="0.85"),
            sa.Column("source", sa.String(50), nullable=False, server_default="ai"),
            sa.Column("document_ids_json", mysql.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("from_kp_id", "to_kp_id", "relation_type"),
            sa.Index("idx_kp_rel_course", "course_id", "relation_type"),
        )
    if "knowledge_point_graphs" not in tables:
        op.create_table(
            "knowledge_point_graphs",
            sa.Column("id", mysql.BIGINT(), autoincrement=True, nullable=False),
            sa.Column("course_id", mysql.BIGINT(), nullable=False),
            sa.Column("version", mysql.INTEGER(), nullable=False, server_default="1"),
            sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
            sa.Column("nodes_json", mysql.JSON(), nullable=True),
            sa.Column("edges_json", mysql.JSON(), nullable=True),
            sa.Column("generated_by", mysql.BIGINT(), nullable=True),
            sa.Column("reviewed_by", mysql.BIGINT(), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.Index("idx_kpg_course_version", "course_id", "version"),
        )

def downgrade() -> None:
    op.drop_table("knowledge_point_graphs")
    op.drop_table("knowledge_point_relations")