"""Store the product composition root type."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260830_13"
down_revision: str | None = "20260827_12"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "component_projects",
        sa.Column(
            "product_type",
            sa.String(length=16),
            nullable=False,
            server_default="machine",
        ),
    )


def downgrade() -> None:
    op.drop_column("component_projects", "product_type")
