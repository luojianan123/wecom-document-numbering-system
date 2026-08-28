"""Store administrator-defined project subject names."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260827_12"
down_revision: str | None = "20260821_11"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    empty_list = sa.text("'[]'")
    with op.batch_alter_table("projects") as batch_op:
        batch_op.add_column(
            sa.Column("product_names", sa.JSON(), nullable=False, server_default=empty_list)
        )
        batch_op.add_column(
            sa.Column("board_names", sa.JSON(), nullable=False, server_default=empty_list)
        )
        batch_op.add_column(
            sa.Column("software_names", sa.JSON(), nullable=False, server_default=empty_list)
        )


def downgrade() -> None:
    with op.batch_alter_table("projects") as batch_op:
        batch_op.drop_column("software_names")
        batch_op.drop_column("board_names")
        batch_op.drop_column("product_names")
