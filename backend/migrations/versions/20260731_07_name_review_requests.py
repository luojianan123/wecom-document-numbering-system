"""新增用户文件名称审核申请。"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260731_07"
down_revision: str | None = "20260729_06"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "name_review_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("requested_by_id", sa.Integer(), nullable=False),
        sa.Column("original_name", sa.Text(), nullable=False),
        sa.Column("proposed_standard_name", sa.Text(), nullable=True),
        sa.Column("issue_summary", sa.Text(), nullable=False),
        sa.Column("similar_names", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("reviewed_name", sa.Text(), nullable=True),
        sa.Column("file_code_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["requested_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["file_code_id"], ["file_codes.id"]),
        sa.ForeignKeyConstraint(["reviewed_by_id"], ["users.id"]),
    )
    op.create_index(
        "ix_name_review_requests_project_id",
        "name_review_requests",
        ["project_id"],
    )
    op.create_index(
        "ix_name_review_requests_requested_by_id",
        "name_review_requests",
        ["requested_by_id"],
    )
    op.create_index(
        "ix_name_review_requests_status",
        "name_review_requests",
        ["status"],
    )
    op.create_index(
        "ix_name_reviews_project_status",
        "name_review_requests",
        ["project_id", "status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_name_reviews_project_status",
        table_name="name_review_requests",
    )
    op.drop_index(
        "ix_name_review_requests_status",
        table_name="name_review_requests",
    )
    op.drop_index(
        "ix_name_review_requests_requested_by_id",
        table_name="name_review_requests",
    )
    op.drop_index(
        "ix_name_review_requests_project_id",
        table_name="name_review_requests",
    )
    op.drop_table("name_review_requests")
