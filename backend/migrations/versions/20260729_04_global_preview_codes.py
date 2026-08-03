"""待确认编号增加全局唯一约束。"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260729_04"
down_revision: str | None = "20260729_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "project_batch_items",
        sa.Column("preview_final_code", sa.String(length=64), nullable=True),
    )

    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            """
            SELECT id, preview_data
            FROM project_batch_items
            WHERE preview_data IS NOT NULL
            """
        )
    ).mappings()
    batch_table = sa.table(
        "project_batch_items",
        sa.column("id", sa.Integer()),
        sa.column("preview_final_code", sa.String(length=64)),
    )
    for row in rows:
        preview_data = row["preview_data"]
        if isinstance(preview_data, str):
            preview_data = json.loads(preview_data)
        final_code = preview_data.get("final_code") if isinstance(preview_data, dict) else None
        if final_code:
            connection.execute(
                sa.update(batch_table)
                .where(batch_table.c.id == row["id"])
                .values(preview_final_code=final_code)
            )

    op.create_index(
        "uq_project_batch_items_preview_final_code",
        "project_batch_items",
        ["preview_final_code"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "uq_project_batch_items_preview_final_code",
        table_name="project_batch_items",
    )
    op.drop_column("project_batch_items", "preview_final_code")
