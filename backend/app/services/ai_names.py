import asyncio
import json
import re
import unicodedata
from pathlib import PurePath

import httpx
from pydantic import BaseModel, Field, ValidationError, field_validator

from ..config import Settings, get_settings
from .document_rules import (
    determine_component_level,
    standardize_document_terms,
)


class NameCorrectionError(ValueError):
    pass


class NameCorrection(BaseModel):
    standard_name: str = Field(min_length=1, max_length=512)
    component_level: str | None = None
    function_code: str | None = None
    stage_keyword: str | None = None

    @field_validator("component_level", mode="before")
    @classmethod
    def validate_level(cls, value: object) -> str | None:
        if value is None or value == "":
            return None
        if isinstance(value, int) and not isinstance(value, bool):
            value = str(value)
        if not isinstance(value, str):
            raise ValueError("部组件级别只能为 2、3、5 或 7")
        value = value.strip()
        if value not in {"2", "3", "5", "7"}:
            raise ValueError("部组件级别只能为 2、3、5 或 7")
        return value

    @field_validator("function_code")
    @classmethod
    def validate_function_code(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        value = value.upper()
        if not re.fullmatch(r"[A-Z]{2}", value):
            raise ValueError("功能代码必须为两位大写字母")
        return value


def normalize_file_name(value: str) -> str:
    value = value.replace("\\", "/").split("/")[-1]
    value = unicodedata.normalize("NFKC", value).strip()
    suffix = PurePath(value).suffix
    if suffix and len(suffix) <= 8:
        value = value[: -len(suffix)]
    value = re.sub(r"\s+", "", value)
    return value


class NameCorrectionService:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    async def correct(self, file_name: str, project_code: str) -> NameCorrection:
        normalized = normalize_file_name(file_name)
        if not normalized:
            raise NameCorrectionError("文件名称不能为空")
        if self.settings.ai_mode == "rules":
            return self._rules_correction(normalized)
        correction = await self._model_correction(normalized, project_code)
        standard_name = standardize_document_terms(normalize_file_name(correction.standard_name))
        return correction.model_copy(
            update={
                "standard_name": standard_name,
                "component_level": determine_component_level(
                    f"{standard_name}{normalized}",
                    correction.component_level,
                ),
            }
        )

    async def correct_many(
        self,
        file_names: list[str],
        project_code: str,
        *,
        concurrency: int = 8,
    ) -> list[NameCorrection | BaseException]:
        """修正一批名称；各名称的模型调用彼此独立，并行执行以缩短批量耗时。

        返回列表顺序与 ``file_names`` 一致，失败项以异常对象占位，
        由调用方决定如何处理；并发通过信号量限制在上限内。
        """
        if not file_names:
            return []
        if len(file_names) == 1:
            return [await self._correct_or_return_error(file_names[0], project_code)]
        semaphore = asyncio.Semaphore(concurrency)

        async def _one(file_name: str) -> NameCorrection | BaseException:
            async with semaphore:
                return await self._correct_or_return_error(file_name, project_code)

        return await asyncio.gather(*(_one(name) for name in file_names))

    async def _correct_or_return_error(
        self,
        file_name: str,
        project_code: str,
    ) -> NameCorrection | BaseException:
        try:
            return await self.correct(file_name, project_code)
        except Exception as exc:  # noqa: BLE001 - 结果以异常对象透传，交由调用方归类
            return exc

    @staticmethod
    def _rules_correction(file_name: str) -> NameCorrection:
        level = determine_component_level(file_name)
        standard_name = standardize_document_terms(file_name)
        stage = "正样件" if "正样件" in file_name else "鉴定件" if "鉴定件" in file_name else None
        return NameCorrection(
            standard_name=standard_name,
            component_level=level,
            stage_keyword=stage,
        )

    async def _model_correction(self, file_name: str, project_code: str) -> NameCorrection:
        base_url = self.settings.ai_api_base_url.rstrip("/")
        url = base_url if base_url.endswith("/chat/completions") else f"{base_url}/chat/completions"
        prompt = (
            "你是企业文件名称标准化助手。只修正明显错别字、空格和不规范写法，"
            "不得改变文件真实含义，standard_name中不得添加项目号。"
            "层级规则：两台及以上计算机或设备组成的系统为2；单台设备为3；"
            "PCBA、仅写板卡或主控板、电源板、控制板、接口板等未明确PCB的板卡文件、"
            "软件、逻辑、操作系统类为5；名称明确包含PCB时为7。"
            "术语必须规范化：逻辑单元集成测试改为仿真测试，"
            "逻辑配置项测试改为确认测试。前缀规则由后端执行：软件简号范围加R-，"
            "评审结论报告加P-，两者叠加为P-R-；不要把前缀写入standard_name。"
            "返回JSON，字段为standard_name、component_level、function_code、"
            "stage_keyword。component_level仅可为2/3/5/7；"
            "function_code为两位大写字母；不确定的候选字段返回null。"
            f"\n项目号：{project_code}\n原始文件名称：{file_name}"
        )
        headers = {
            "Authorization": f"Bearer {self.settings.ai_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.settings.ai_model,
            "messages": [
                {"role": "system", "content": "严格返回JSON对象，不输出解释。"},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=45) as client:
                    response = await client.post(url, headers=headers, json=payload)
                    response.raise_for_status()
                    data = response.json()
                content = data["choices"][0]["message"]["content"]
                content = re.sub(r"^```(?:json)?|```$", "", content.strip(), flags=re.IGNORECASE)
                return NameCorrection.model_validate(json.loads(content))
            except httpx.TransportError as exc:
                # 连接中断/超时等瞬时错误：重试，避免个别名称直接判失败。
                last_error = exc
                if attempt < 2:
                    await asyncio.sleep(0.6 * (attempt + 1))
                    continue
            except (
                httpx.HTTPError,
                KeyError,
                IndexError,
                json.JSONDecodeError,
                ValidationError,
            ) as exc:
                last_error = exc
                break
        assert last_error is not None
        detail = str(last_error) or "无详细信息"
        raise NameCorrectionError(
            f"AI 文件名修正失败（{type(last_error).__name__}）：{detail}"
        ) from last_error
