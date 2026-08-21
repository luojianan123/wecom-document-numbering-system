"""Add product component coding tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260821_11"
down_revision: str | None = "20260803_10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "component_projects",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_code", sa.String(length=4), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_code", name="uq_component_projects_code"),
    )
    op.create_index(
        "ix_component_projects_project_code",
        "component_projects",
        ["project_code"],
        unique=True,
    )
    op.create_table(
        "component_nodes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("component_project_id", sa.Integer(), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("code", sa.String(length=128), nullable=False),
        sa.Column("stage", sa.String(length=1), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["component_project_id"], ["component_projects.id"]),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["parent_id"], ["component_nodes.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "component_project_id", "code", name="uq_component_nodes_code"
        ),
    )
    op.create_index(
        "ix_component_nodes_project",
        "component_nodes",
        ["component_project_id"],
    )
    op.create_table(
        "component_claims",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("component_node_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("claimant_name", sa.String(length=128), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["component_node_id"], ["component_nodes.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_component_claims_node", "component_claims", ["component_node_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_component_claims_node", table_name="component_claims")
    op.drop_table("component_claims")
    op.drop_index("ix_component_nodes_project", table_name="component_nodes")
    op.drop_table("component_nodes")
    op.drop_index(
        "ix_component_projects_project_code", table_name="component_projects"
    )
    op.drop_table("component_projects")
