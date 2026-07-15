"""Add explanation column to questions for answer analysis."""
from alembic import op
import sqlalchemy as sa

revision = "0010_question_explanation"
down_revision = "0009_submission_attempts"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if "explanation" not in {column["name"] for column in inspector.get_columns("questions")}:
        op.add_column("questions", sa.Column("explanation", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("questions", "explanation")
