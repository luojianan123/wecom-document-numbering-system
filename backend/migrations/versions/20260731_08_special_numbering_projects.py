"""新增特殊编号项目标识。"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260731_08"
down_revision: str | None = "20260731_07"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column(
            "special_numbering",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("projects", "special_numbering")
