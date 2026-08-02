"""保存领取人姓名快照并为领取记录增加查询索引。"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260802_09"
down_revision: str | None = "20260731_08"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "code_claims",
        sa.Column("claimant_name", sa.String(length=128), nullable=True),
    )
    op.execute(
        sa.text(
            """
            UPDATE code_claims
            SET claimant_name = COALESCE(
                (SELECT users.name FROM users WHERE users.id = code_claims.user_id),
                ''
            )
            """
        )
    )
    with op.batch_alter_table("code_claims") as batch_op:
        batch_op.alter_column(
            "claimant_name",
            existing_type=sa.String(length=128),
            nullable=False,
        )
    op.create_index(
        "ix_code_claims_file_code_id",
        "code_claims",
        ["file_code_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_code_claims_file_code_id", table_name="code_claims")
    with op.batch_alter_table("code_claims") as batch_op:
        batch_op.drop_column("claimant_name")
