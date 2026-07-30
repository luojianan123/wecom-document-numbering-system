"""批量编码先暂存预览，确认后再写入正式编码表。"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260729_03"
down_revision: str | None = "20260729_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "project_batch_items",
        sa.Column("preview_data", sa.JSON(), nullable=True),
    )

    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            """
            SELECT
                batch.id AS batch_id,
                batch.file_code_id,
                projects.status AS project_status,
                codes.original_name,
                codes.standard_name,
                codes.segment_a,
                codes.segment_b,
                codes.segment_c,
                codes.segment_d,
                codes.segment_e,
                codes.segment_f,
                codes.segment_g,
                codes.segment_h,
                codes.final_code
            FROM project_batch_items AS batch
            JOIN projects ON projects.id = batch.project_id
            JOIN file_codes AS codes ON codes.id = batch.file_code_id
            """
        )
    ).mappings()

    batch_table = sa.table(
        "project_batch_items",
        sa.column("id", sa.Integer()),
        sa.column("file_code_id", sa.Integer()),
        sa.column("preview_data", sa.JSON()),
    )
    draft_code_ids: list[int] = []
    for row in rows:
        preview_data = {
            "original_name": row["original_name"],
            "standard_name": row["standard_name"],
            "segment_a": row["segment_a"],
            "segment_b": row["segment_b"],
            "segment_c": row["segment_c"],
            "segment_d": row["segment_d"],
            "segment_e": row["segment_e"],
            "segment_f": row["segment_f"],
            "segment_g": row["segment_g"],
            "segment_h": row["segment_h"],
            "final_code": row["final_code"],
        }
        values: dict[str, object] = {"preview_data": preview_data}
        if row["project_status"] == "draft":
            values["file_code_id"] = None
            draft_code_ids.append(row["file_code_id"])
        connection.execute(
            sa.update(batch_table)
            .where(batch_table.c.id == row["batch_id"])
            .values(**values)
        )

    if draft_code_ids:
        claims_table = sa.table(
            "code_claims",
            sa.column("file_code_id", sa.Integer()),
        )
        codes_table = sa.table(
            "file_codes",
            sa.column("id", sa.Integer()),
        )
        connection.execute(
            sa.delete(claims_table).where(
                claims_table.c.file_code_id.in_(draft_code_ids)
            )
        )
        connection.execute(
            sa.delete(codes_table).where(codes_table.c.id.in_(draft_code_ids))
        )


def downgrade() -> None:
    op.drop_column("project_batch_items", "preview_data")
