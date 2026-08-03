"""保存用户提交的新项目编号申请。"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260803_10"
down_revision: str | None = "20260802_09"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "project_number_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_code", sa.String(length=4), nullable=False),
        sa.Column("requested_by_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("processed_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["processed_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["requested_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_project_number_requests_project_code",
        "project_number_requests",
        ["project_code"],
    )
    op.create_index(
        "ix_project_number_requests_requested_by_id",
        "project_number_requests",
        ["requested_by_id"],
    )
    op.create_index(
        "ix_project_number_requests_status",
        "project_number_requests",
        ["status"],
    )
    op.create_index(
        "ix_project_number_requests_status_created",
        "project_number_requests",
        ["status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_project_number_requests_status_created",
        table_name="project_number_requests",
    )
    op.drop_index(
        "ix_project_number_requests_status",
        table_name="project_number_requests",
    )
    op.drop_index(
        "ix_project_number_requests_requested_by_id",
        table_name="project_number_requests",
    )
    op.drop_index(
        "ix_project_number_requests_project_code",
        table_name="project_number_requests",
    )
    op.drop_table("project_number_requests")
