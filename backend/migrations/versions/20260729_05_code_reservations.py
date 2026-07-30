"""用统一占用表保证待确认与正式编号全局唯一。"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260729_05"
down_revision: str | None = "20260729_04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "code_reservations",
        sa.Column("final_code", sa.String(length=64), primary_key=True),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
    )
    op.create_index(
        "ix_code_reservations_project_id",
        "code_reservations",
        ["project_id"],
    )

    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            INSERT INTO code_reservations (final_code, project_id, created_at)
            SELECT final_code, project_id, created_at
            FROM file_codes
            """
        )
    )
    connection.execute(
        sa.text(
            """
            INSERT INTO code_reservations (final_code, project_id, created_at)
            SELECT
                batch.preview_final_code,
                batch.project_id,
                batch.created_at
            FROM project_batch_items AS batch
            WHERE batch.preview_final_code IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1
                  FROM code_reservations AS reservations
                  WHERE reservations.final_code = batch.preview_final_code
              )
            """
        )
    )


def downgrade() -> None:
    op.drop_index(
        "ix_code_reservations_project_id",
        table_name="code_reservations",
    )
    op.drop_table("code_reservations")
