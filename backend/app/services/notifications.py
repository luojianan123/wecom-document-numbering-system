import logging

from ..config import get_settings
from .wecom import wecom_client

logger = logging.getLogger(__name__)


async def _send_if_live(user_ids: list[str], content: str) -> None:
    settings = get_settings()
    if settings.wecom_auth_mode != "live":
        return
    if not user_ids:
        logger.warning("未配置企业微信消息接收人，消息未发送")
        return
    try:
        await wecom_client.send_text_message(user_ids, content)
    except Exception:
        # 业务数据已经提交；消息网关异常不能把成功操作变成接口失败。
        logger.exception("企业微信提醒发送失败")


async def notify_admin_review_requested(
    *,
    review_id: int,
    project_code: str,
    project_name: str,
    requester_name: str,
    requester_user_id: str,
    requested_name: str,
    issue_summary: str,
) -> None:
    settings = get_settings()
    content = "\n".join(
        [
            "【文件编号申请待审核】",
            f"申请人：{requester_name}（{requester_user_id}）",
            f"项目：{project_code} {project_name}",
            f"文件名称：{requested_name}",
            f"待审原因：{issue_summary}",
            f"申请编号：{review_id}",
            f"审核入口：{settings.frontend_url.rstrip('/')}/admin",
        ]
    )
    await _send_if_live(settings.wecom_admin_user_id_list, content)


async def notify_review_approved(
    *,
    recipient_user_id: str,
    recipient_name: str,
    project_code: str,
    project_name: str,
    reviewed_name: str,
    final_code: str,
) -> None:
    settings = get_settings()
    content = "\n".join(
        [
            "【文件编号申请已通过】",
            f"{recipient_name}，您的编号申请已审核通过。",
            f"项目：{project_code} {project_name}",
            f"文件名称：{reviewed_name}",
            f"文件编号：{final_code}",
            f"查看入口：{settings.frontend_url.rstrip('/')}/user",
        ]
    )
    await _send_if_live([recipient_user_id], content)
