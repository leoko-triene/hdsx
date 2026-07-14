"""Add teacher answer corrections and user notifications."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0007_classroom_ops"
down_revision = "0006_assignment_material"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    return column in {c["name"] for c in inspect(op.get_bind()).get_columns(table)}


def _table_exists(name: str) -> bool:
    return name in inspect(op.get_bind()).get_table_names()


def _index_exists(table: str, name: str) -> bool:
    return name in {idx["name"] for idx in inspect(op.get_bind()).get_indexes(table)}


def _fk_exists(table: str, name: str) -> bool:
    return name in {fk["name"] for fk in inspect(op.get_bind()).get_foreign_keys(table)}


def upgrade():
    if not _has_column("qa_messages", "original_content"):
        op.add_column("qa_messages", sa.Column("original_content", sa.Text(), nullable=True))
    if not _has_column("qa_messages", "correction_note"):
        op.add_column("qa_messages", sa.Column("correction_note", sa.String(500), nullable=True))
    if not _has_column("qa_messages", "corrected_by"):
        op.add_column("qa_messages", sa.Column("corrected_by", sa.BigInteger(), nullable=True))
    if not _has_column("qa_messages", "corrected_at"):
        op.add_column("qa_messages", sa.Column("corrected_at", sa.DateTime(), nullable=True))
    if not _fk_exists("qa_messages", "fk_qa_messages_corrected_by_users"):
        op.create_foreign_key("fk_qa_messages_corrected_by_users", "qa_messages", "users", ["corrected_by"], ["id"])

    if not _table_exists("notifications"):
        op.create_table(
            "notifications",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("user_id", sa.BigInteger(), nullable=False),
            sa.Column("notification_type", sa.String(50), nullable=False),
            sa.Column("title", sa.String(255), nullable=False),
            sa.Column("content", sa.String(1000), nullable=False),
            sa.Column("link", sa.String(500), nullable=True),
            sa.Column("notification_key", sa.String(180), nullable=False),
            sa.Column("read_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("notification_key"),
        )
    if not _index_exists("notifications", "ix_notifications_user_id"):
        op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    if not _index_exists("notifications", "ix_notifications_notification_type"):
        op.create_index("ix_notifications_notification_type", "notifications", ["notification_type"])
    if not _index_exists("notifications", "ix_notifications_read_at"):
        op.create_index("ix_notifications_read_at", "notifications", ["read_at"])


def downgrade():
    op.drop_table("notifications")
    if _fk_exists("qa_messages", "fk_qa_messages_corrected_by_users"):
        op.drop_constraint("fk_qa_messages_corrected_by_users", "qa_messages", type_="foreignkey")
    for col in ["corrected_at", "corrected_by", "correction_note", "original_content"]:
        if _has_column("qa_messages", col):
            op.drop_column("qa_messages", col)
