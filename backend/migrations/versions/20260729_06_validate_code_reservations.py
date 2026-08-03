"""校验历史编号占用与项目状态一致性。"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260729_06"
down_revision: str | None = "20260729_05"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _count(connection: sa.Connection, sql: str) -> int:
    return int(connection.scalar(sa.text(sql)) or 0)


def upgrade() -> None:
    connection = op.get_bind()

    conflicting_allocations = _count(
        connection,
        """
        SELECT COUNT(*)
        FROM project_batch_items AS batch
        JOIN file_codes AS code
          ON code.final_code = batch.preview_final_code
        WHERE batch.file_code_id IS NULL
           OR batch.file_code_id <> code.id
           OR batch.project_id <> code.project_id
        """,
    )
    active_pending_previews = _count(
        connection,
        """
        SELECT COUNT(*)
        FROM project_batch_items AS batch
        JOIN projects AS project ON project.id = batch.project_id
        WHERE project.status = 'active'
          AND batch.success = true
          AND batch.preview_final_code IS NOT NULL
          AND batch.file_code_id IS NULL
        """,
    )
    missing_reservations = _count(
        connection,
        """
        SELECT COUNT(*)
        FROM (
            SELECT final_code, project_id FROM file_codes
            UNION
            SELECT preview_final_code, project_id
            FROM project_batch_items
            WHERE preview_final_code IS NOT NULL
        ) AS allocated
        LEFT JOIN code_reservations AS reservation
          ON reservation.final_code = allocated.final_code
         AND reservation.project_id = allocated.project_id
        WHERE reservation.final_code IS NULL
        """,
    )
    orphan_reservations = _count(
        connection,
        """
        SELECT COUNT(*)
        FROM code_reservations AS reservation
        LEFT JOIN (
            SELECT final_code, project_id FROM file_codes
            UNION
            SELECT preview_final_code, project_id
            FROM project_batch_items
            WHERE preview_final_code IS NOT NULL
        ) AS allocated
          ON allocated.final_code = reservation.final_code
         AND allocated.project_id = reservation.project_id
        WHERE allocated.final_code IS NULL
        """,
    )

    problems = {
        "跨记录重复分配": conflicting_allocations,
        "已启用项目遗留待确认编码": active_pending_previews,
        "缺失占号记录": missing_reservations,
        "孤立占号记录": orphan_reservations,
    }
    details = "；".join(f"{name} {count} 条" for name, count in problems.items() if count)
    if details:
        raise RuntimeError(f"历史编号数据校验失败：{details}，请先修复后再升级")


def downgrade() -> None:
    pass
