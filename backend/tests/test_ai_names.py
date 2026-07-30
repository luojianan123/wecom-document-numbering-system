import asyncio

import pytest

from app.config import Settings
from app.services.ai_names import NameCorrection, NameCorrectionService


@pytest.mark.parametrize(
    ("raw_level", "expected"),
    [(2, "2"), (3, "3"), (5, "5"), (7, "7"), (" 5 ", "5")],
)
def test_name_correction_accepts_numeric_or_string_level(
    raw_level: object,
    expected: str,
) -> None:
    result = NameCorrection.model_validate(
        {
            "standard_name": "控制软件质量保证计划",
            "component_level": raw_level,
        }
    )

    assert result.component_level == expected


def test_openai_compatible_name_correction_validates_structured_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "choices": [
                    {
                        "message": {
                            "content": (
                                "```json\n"
                                '{"standard_name":"1234控制模块技术要求",'
                                '"component_level":3,"function_code":"KZ",'
                                '"stage_keyword":null}'
                                "\n```"
                            )
                        }
                    }
                ]
            }

    class FakeAsyncClient:
        def __init__(self, **_: object):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

        async def post(self, url: str, **kwargs: object) -> FakeResponse:
            captured["url"] = url
            captured.update(kwargs)
            return FakeResponse()

    monkeypatch.setattr("app.services.ai_names.httpx.AsyncClient", FakeAsyncClient)
    service = NameCorrectionService(
        Settings(
            ai_mode="openai_compatible",
            ai_api_base_url="https://ai.example.com/v1",
            ai_api_key="test-key",
            ai_model="approved-model",
        )
    )

    result = asyncio.run(service.correct(" 1234 控制模块技术要求.docx ", "1234"))

    assert result.standard_name == "1234控制模块技术要求"
    assert result.component_level == "3"
    assert result.function_code == "KZ"
    assert captured["url"] == "https://ai.example.com/v1/chat/completions"
    assert captured["headers"] == {
        "Authorization": "Bearer test-key",
        "Content-Type": "application/json",
    }
    payload = captured["json"]
    assert isinstance(payload, dict)
    messages = payload["messages"]
    assert isinstance(messages, list)
    prompt = messages[1]["content"]
    for expected_rule in (
        "仅写板卡",
        "软件、逻辑、操作系统类为5",
        "逻辑单元集成测试改为仿真测试",
        "逻辑配置项测试改为确认测试",
        "两者叠加为P-R-",
    ):
        assert expected_rule in prompt


def test_model_level_is_overridden_by_deterministic_positive_rule(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_model_correction(
        _self: NameCorrectionService,
        _file_name: str,
        _project_code: str,
    ):
        from app.services.ai_names import NameCorrection

        return NameCorrection(
            standard_name="控制逻辑图",
            component_level="7",
            function_code="KZ",
        )

    monkeypatch.setattr(
        NameCorrectionService,
        "_model_correction",
        fake_model_correction,
    )
    service = NameCorrectionService(
        Settings(
            ai_mode="openai_compatible",
            ai_api_base_url="https://ai.example.com/v1",
            ai_api_key="test-key",
            ai_model="approved-model",
        )
    )

    result = asyncio.run(service.correct("控制逻辑图", "1234"))

    assert result.component_level == "5"


@pytest.mark.parametrize(
    ("file_name", "standard_name", "component_level"),
    [
        ("控制板卡电装要求.docx", "控制板卡电装要求", "5"),
        ("控制逻辑图", "控制逻辑图", "5"),
        ("控制操作系统镜像文件", "控制操作系统镜像文件", "5"),
        (
            "控制逻辑单元集成测试计划",
            "控制仿真测试计划",
            "5",
        ),
        (
            "控制逻辑配置项测试报告",
            "控制确认测试报告",
            "5",
        ),
        ("控制PCB板卡加工要求", "控制PCB板卡加工要求", "7"),
        ("控制PCB逻辑加工要求", "控制PCB逻辑加工要求", "7"),
        (
            "3台计算机组成的通信系统技术要求",
            "3台计算机组成的通信系统技术要求",
            "2",
        ),
        (
            "2台设备组成的通信系统技术要求",
            "2台设备组成的通信系统技术要求",
            "2",
        ),
        (
            "两个及以上文件汇总表",
            "两个及以上文件汇总表",
            "3",
        ),
        (
            "一台设备产品技术要求",
            "一台设备产品技术要求",
            "3",
        ),
        (
            "一台设备系统级测试报告",
            "一台设备系统级测试报告",
            "3",
        ),
        (
            "3台设备检验报告",
            "3台设备检验报告",
            "3",
        ),
        (
            "十一台计算机组成的系统技术要求",
            "十一台计算机组成的系统技术要求",
            "2",
        ),
        (
            "二十一台计算机组成的系统技术要求",
            "二十一台计算机组成的系统技术要求",
            "2",
        ),
        (
            "两台高性能计算机组成的系统技术要求",
            "两台高性能计算机组成的系统技术要求",
            "2",
        ),
    ],
)
def test_rule_correction_applies_positive_rules(
    file_name: str,
    standard_name: str,
    component_level: str,
) -> None:
    service = NameCorrectionService(Settings(ai_mode="rules"))

    result = asyncio.run(service.correct(file_name, "1234"))

    assert result.standard_name == standard_name
    assert result.component_level == component_level
