import asyncio
from urllib.parse import parse_qs, urlparse

import pytest

from app.config import Settings
from app.services.wecom import WeComClient


def test_builds_enterprise_wecom_qr_url() -> None:
    client = WeComClient(
        Settings(
            wecom_auth_mode="live",
            wecom_corp_id="ww-corp-id",
            wecom_agent_id="1000002",
            wecom_corp_secret="secret",
        )
    )

    url = client.build_qr_authorization_url(
        "https://codes.example.com/api/auth/wecom/qr/callback",
        "one-time-state",
    )
    parsed = urlparse(url)
    query = parse_qs(parsed.query)

    assert parsed.netloc == "open.work.weixin.qq.com"
    assert query["appid"] == ["ww-corp-id"]
    assert query["agentid"] == ["1000002"]
    assert query["redirect_uri"] == ["https://codes.example.com/api/auth/wecom/qr/callback"]
    assert query["state"] == ["one-time-state"]


def test_live_mode_requires_all_wecom_credentials() -> None:
    settings = Settings(
        _env_file=None,
        wecom_auth_mode="live",
        wecom_corp_id="",
        wecom_agent_id="",
        wecom_corp_secret="",
    )

    with pytest.raises(RuntimeError, match="WECOM_CORP_ID"):
        settings.validate_runtime_secrets()


def test_admin_user_ids_are_trimmed_and_case_insensitive() -> None:
    settings = Settings(
        _env_file=None,
        wecom_admin_user_ids=" JingPing.Li, luojianan ",
    )

    assert settings.wecom_admin_user_id_list == ["JingPing.Li", "luojianan"]
    assert settings.wecom_admin_user_id_set == {"jingping.li", "luojianan"}


def test_production_requires_secure_https_session() -> None:
    settings = Settings(
        app_env="production",
        session_secret="x" * 32,
        cookie_secure=False,
        frontend_url="http://codes.example.com",
        backend_public_url="http://codes.example.com",
    )

    with pytest.raises(RuntimeError, match="COOKIE_SECURE"):
        settings.validate_runtime_secrets()


def test_exchanges_code_for_user_id_and_caches_access_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = [
        {"errcode": 0, "access_token": "cached-token", "expires_in": 7200},
        {"errcode": 40029, "errmsg": "invalid code for first endpoint"},
        {"errcode": 0, "UserId": "zhangsan"},
        {"errcode": 0, "userid": "lisi"},
    ]
    requested_urls: list[str] = []

    class FakeResponse:
        def __init__(self, data: dict[str, object]):
            self.data = data

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return self.data

    class FakeAsyncClient:
        def __init__(self, **_: object):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

        async def get(self, url: str, **_: object) -> FakeResponse:
            requested_urls.append(url)
            return FakeResponse(responses.pop(0))

    monkeypatch.setattr("app.services.wecom.httpx.AsyncClient", FakeAsyncClient)
    client = WeComClient(
        Settings(
            wecom_auth_mode="live",
            wecom_corp_id="ww-corp-id",
            wecom_agent_id="1000002",
            wecom_corp_secret="secret",
        )
    )

    assert asyncio.run(client.get_user_id("first-code")) == "zhangsan"
    assert asyncio.run(client.get_user_id("second-code")) == "lisi"
    assert sum(url.endswith("/cgi-bin/gettoken") for url in requested_urls) == 1


def test_fetches_wecom_display_name(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = [
        {"errcode": 0, "access_token": "cached-token", "expires_in": 7200},
        {"errcode": 0, "userid": "jingping.li"},
        {"errcode": 0, "userid": "jingping.li", "name": "李京平"},
    ]
    requested_urls: list[str] = []

    class FakeResponse:
        def __init__(self, data: dict[str, object]):
            self.data = data

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return self.data

    class FakeAsyncClient:
        def __init__(self, **_: object):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

        async def get(self, url: str, **_: object) -> FakeResponse:
            requested_urls.append(url)
            return FakeResponse(responses.pop(0))

    monkeypatch.setattr("app.services.wecom.httpx.AsyncClient", FakeAsyncClient)
    client = WeComClient(
        Settings(
            _env_file=None,
            wecom_auth_mode="live",
            wecom_corp_id="ww-corp-id",
            wecom_agent_id="1000002",
            wecom_corp_secret="secret",
            wecom_admin_user_ids="jingping.li",
        )
    )

    assert asyncio.run(client.get_user_identity("login-code")) == (
        "jingping.li",
        "李京平",
    )
    assert requested_urls[-1].endswith("/cgi-bin/user/get")


def test_sends_wecom_text_application_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requested_payloads: list[dict[str, object]] = []

    class FakeResponse:
        def __init__(self, data: dict[str, object]):
            self.data = data

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return self.data

    class FakeAsyncClient:
        def __init__(self, **_: object):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

        async def get(self, *_: object, **__: object) -> FakeResponse:
            return FakeResponse({"errcode": 0, "access_token": "token", "expires_in": 7200})

        async def post(
            self,
            _: str,
            *,
            json: dict[str, object],
            **__: object,
        ) -> FakeResponse:
            requested_payloads.append(json)
            return FakeResponse({"errcode": 0, "errmsg": "ok", "msgid": "1"})

    monkeypatch.setattr("app.services.wecom.httpx.AsyncClient", FakeAsyncClient)
    client = WeComClient(
        Settings(
            _env_file=None,
            wecom_auth_mode="live",
            wecom_corp_id="ww-corp-id",
            wecom_agent_id="1000002",
            wecom_corp_secret="secret",
            wecom_admin_user_ids="jingping.li,luojianan",
        )
    )

    result = asyncio.run(
        client.send_text_message(
            ["jingping.li", "luojianan", "jingping.li"],
            "有新的编号申请",
        )
    )

    assert result["errcode"] == 0
    assert requested_payloads == [
        {
            "touser": "jingping.li|luojianan",
            "msgtype": "text",
            "agentid": 1000002,
            "text": {"content": "有新的编号申请"},
            "safe": 0,
            "enable_duplicate_check": 1,
            "duplicate_check_interval": 600,
        }
    ]
