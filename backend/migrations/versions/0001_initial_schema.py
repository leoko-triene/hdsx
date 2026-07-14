"""Initial MySQL schema baseline."""
from alembic import op

from app.db.base import Base
from app.modules import models  # noqa: F401

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # 基线迁移从受版本控制的 SQLAlchemy metadata 创建全部表；后续变更必须使用显式 op。
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade():
    Base.metadata.drop_all(bind=op.get_bind(), checkfirst=True)

