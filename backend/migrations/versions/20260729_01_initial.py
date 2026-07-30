"""建立第一阶段数据表。"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260729_01"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("wecom_user_id", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("wecom_user_id"),
    )
    op.create_index("ix_users_wecom_user_id", "users", ["wecom_user_id"])

    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_code", sa.String(length=4), nullable=False),
        sa.Column("project_name", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.UniqueConstraint("project_code"),
    )
    op.create_index("ix_projects_project_code", "projects", ["project_code"])

    op.create_table(
        "file_codes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("original_name", sa.Text(), nullable=False),
        sa.Column("standard_name", sa.Text(), nullable=False),
        sa.Column("segment_a", sa.String(length=8), nullable=False),
        sa.Column("segment_b", sa.String(length=8), nullable=False),
        sa.Column("segment_c", sa.String(length=8), nullable=False),
        sa.Column("segment_d", sa.String(length=8), nullable=False),
        sa.Column("segment_e", sa.String(length=8), nullable=False),
        sa.Column("segment_f", sa.String(length=16), nullable=False),
        sa.Column("segment_g", sa.String(length=8), nullable=False),
        sa.Column("segment_h", sa.String(length=8), nullable=False),
        sa.Column("final_code", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.UniqueConstraint("final_code"),
        sa.UniqueConstraint(
            "project_id",
            "standard_name",
            name="uq_project_standard_name",
        ),
    )
    op.create_index("ix_file_codes_final_code", "file_codes", ["final_code"])
    op.create_index(
        "ix_file_codes_project_enabled",
        "file_codes",
        ["project_id", "enabled"],
    )

    op.create_table(
        "code_claims",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("file_code_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["file_code_id"], ["file_codes.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )

    op.create_table(
        "auth_states",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("state_hash", sa.String(length=64), nullable=False),
        sa.Column("purpose", sa.String(length=16), nullable=False),
        sa.Column("return_path", sa.String(length=512), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("state_hash"),
    )
    op.create_index("ix_auth_states_state_hash", "auth_states", ["state_hash"])


def downgrade() -> None:
    op.drop_index("ix_auth_states_state_hash", table_name="auth_states")
    op.drop_table("auth_states")
    op.drop_table("code_claims")
    op.drop_index("ix_file_codes_project_enabled", table_name="file_codes")
    op.drop_index("ix_file_codes_final_code", table_name="file_codes")
    op.drop_table("file_codes")
    op.drop_index("ix_projects_project_code", table_name="projects")
    op.drop_table("projects")
    op.drop_index("ix_users_wecom_user_id", table_name="users")
    op.drop_table("users")

