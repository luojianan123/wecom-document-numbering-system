import asyncio
import time
from urllib.parse import urlencode

import httpx

from ..config import Settings, get_settings


class WeComError(ValueError):
    pass


class WeComClient:
    API_BASE = "https://qyapi.weixin.qq.com"
    QR_BASE = "https://open.work.weixin.qq.com/wwopen/sso/qrConnect"

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self._access_token = ""
        self._access_token_expires_at = 0.0
        self._token_lock = asyncio.Lock()

    def build_qr_authorization_url(self, redirect_uri: str, state: str) -> str:
        params = {
            "appid": self.settings.wecom_corp_id,
            "agentid": self.settings.wecom_agent_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "lang": "zh",
        }
        return f"{self.QR_BASE}?{urlencode(params)}"

    async def _get_access_token(self) -> str:
        now = time.monotonic()
        if self._access_token and now < self._access_token_expires_at:
            return self._access_token
        async with self._token_lock:
            now = time.monotonic()
            if self._access_token and now < self._access_token_expires_at:
                return self._access_token
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    f"{self.API_BASE}/cgi-bin/gettoken",
                    params={
                        "corpid": self.settings.wecom_corp_id,
                        "corpsecret": self.settings.wecom_corp_secret,
                    },
                )
                response.raise_for_status()
                data = response.json()
            if data.get("errcode") != 0:
                raise WeComError(
                    f"获取企业微信 access_token 失败："
                    f"{data.get('errcode')} {data.get('errmsg', '')}"
                )
            self._access_token = data["access_token"]
            expires_in = int(data.get("expires_in", 7200))
            self._access_token_expires_at = time.monotonic() + max(expires_in - 300, 60)
            return self._access_token

    async def get_user_id(self, code: str) -> str:
        access_token = await self._get_access_token()
        paths = ("/cgi-bin/auth/getuserinfo", "/cgi-bin/user/getuserinfo")
        last_error = ""
        async with httpx.AsyncClient(timeout=10) as client:
            for path in paths:
                response = await client.get(
                    f"{self.API_BASE}{path}",
                    params={"access_token": access_token, "code": code},
                )
                response.raise_for_status()
                data = response.json()
                if data.get("errcode") == 0:
                    user_id = data.get("userid") or data.get("UserId")
                    if not user_id:
                        raise WeComError("扫码成员不是当前企业的可访问成员")
                    return str(user_id)
                last_error = f"{data.get('errcode')} {data.get('errmsg', '')}"
        raise WeComError(f"获取企业微信成员身份失败：{last_error}")


wecom_client = WeComClient()

