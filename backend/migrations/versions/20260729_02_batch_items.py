"""持久化管理员批量生成结果。"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260729_02"
down_revision: str | None = "20260729_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "project_batch_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("original_name", sa.Text(), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("file_code_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["file_code_id"], ["file_codes.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
    )
    op.create_index(
        "ix_project_batch_items_project_id",
        "project_batch_items",
        ["project_id"],
    )

    connection = op.get_bind()
    projects = connection.execute(sa.text("SELECT id FROM projects")).scalars()
    for project_id in projects:
        connection.execute(
            sa.text(
                """
                INSERT INTO project_batch_items (
                    project_id, original_name, success, error, file_code_id,
                    created_at, updated_at
                )
                SELECT
                    project_id, original_name, true, NULL, id,
                    created_at, created_at
                FROM file_codes
                WHERE project_id = :project_id AND source = 'admin_batch'
                """
            ),
            {"project_id": project_id},
        )


def downgrade() -> None:
    op.drop_index(
        "ix_project_batch_items_project_id",
        table_name="project_batch_items",
    )
    op.drop_table("project_batch_items")
