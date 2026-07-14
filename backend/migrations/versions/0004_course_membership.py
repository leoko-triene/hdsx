"""Add multiple course managers, direct members and join requests."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0004_course_membership"
down_revision = "0003_document_dedup"
branch_labels = None
depends_on = None


def _table_exists(name: str) -> bool:
    return name in inspect(op.get_bind()).get_table_names()


def _index_exists(table: str, name: str) -> bool:
    return name in {idx["name"] for idx in inspect(op.get_bind()).get_indexes(table)}


def upgrade():
    if not _table_exists("course_managers"):
        op.create_table(
            "course_managers",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("course_id", sa.BigInteger(), nullable=False),
            sa.Column("user_id", sa.BigInteger(), nullable=False),
            sa.Column("added_by", sa.BigInteger(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["course_id"], ["courses.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["added_by"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("course_id", "user_id"),
        )
    if not _index_exists("course_managers", "ix_course_managers_course_id"):
        op.create_index("ix_course_managers_course_id", "course_managers", ["course_id"])
    if not _index_exists("course_managers", "ix_course_managers_user_id"):
        op.create_index("ix_course_managers_user_id", "course_managers", ["user_id"])

    if not _table_exists("course_members"):
        op.create_table(
            "course_members",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("course_id", sa.BigInteger(), nullable=False),
            sa.Column("student_id", sa.BigInteger(), nullable=False),
            sa.Column("source", sa.String(30), nullable=False, server_default="approved"),
            sa.Column("status", sa.String(30), nullable=False, server_default="active"),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["course_id"], ["courses.id"]),
            sa.ForeignKeyConstraint(["student_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("course_id", "student_id"),
        )
    if not _index_exists("course_members", "ix_course_members_course_id"):
        op.create_index("ix_course_members_course_id", "course_members", ["course_id"])
    if not _index_exists("course_members", "ix_course_members_student_id"):
        op.create_index("ix_course_members_student_id", "course_members", ["student_id"])

    if not _table_exists("course_join_requests"):
        op.create_table(
            "course_join_requests",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("course_id", sa.BigInteger(), nullable=False),
            sa.Column("student_id", sa.BigInteger(), nullable=False),
            sa.Column("reason", sa.String(500), nullable=True),
            sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
            sa.Column("reviewer_id", sa.BigInteger(), nullable=True),
            sa.Column("review_comment", sa.String(500), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["course_id"], ["courses.id"]),
            sa.ForeignKeyConstraint(["student_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("course_id", "student_id"),
        )
    if not _index_exists("course_join_requests", "ix_course_join_requests_course_id"):
        op.create_index("ix_course_join_requests_course_id", "course_join_requests", ["course_id"])
    if not _index_exists("course_join_requests", "ix_course_join_requests_student_id"):
        op.create_index("ix_course_join_requests_student_id", "course_join_requests", ["student_id"])
    if not _index_exists("course_join_requests", "ix_course_join_requests_status"):
        op.create_index("ix_course_join_requests_status", "course_join_requests", ["status"])

    op.execute("INSERT IGNORE INTO course_managers (course_id,user_id,added_by) SELECT id,owner_id,owner_id FROM courses")
    op.execute("INSERT IGNORE INTO course_members (course_id,student_id,source,status) SELECT DISTINCT a.course_id,s.student_id,'existing_submission','active' FROM submissions s JOIN assignments a ON a.id=s.assignment_id")


def downgrade():
    op.drop_table("course_join_requests")
    op.drop_table("course_members")
    op.drop_table("course_managers")
