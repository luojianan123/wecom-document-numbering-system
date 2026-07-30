from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from ..config import get_settings


class RuleConfigError(ValueError):
    pass


@dataclass(frozen=True)
class RuleConfig:
    name: str
    version: str
    segment_a: str
    segment_e: str
    with_stage_format: str
    without_stage_format: str


def load_rule_config(path: Path) -> RuleConfig:
    if not path.is_file():
        raise RuleConfigError(f"编号规则文件不存在：{path}")

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise RuleConfigError(f"编号规则文件无法读取：{exc}") from exc

    try:
        config = RuleConfig(
            name=str(raw["rule"]["name"]),
            version=str(raw["rule"]["version"]),
            segment_a=str(raw["segments"]["A"]["value"]),
            segment_e=str(raw["segments"]["E"]["value"]),
            with_stage_format=str(raw["format"]["with_stage"]),
            without_stage_format=str(raw["format"]["without_stage"]),
        )
    except (KeyError, TypeError) as exc:
        raise RuleConfigError(f"编号规则文件缺少关键字段：{exc}") from exc

    expected = {
        "A段固定值": (config.segment_a, "GH"),
        "E段固定值": (config.segment_e, "010"),
        "有阶段号格式": (
            config.with_stage_format,
            "{A}{B}-{C}{D}-{E}{F}-{G}-{H}",
        ),
        "无阶段号格式": (
            config.without_stage_format,
            "{A}{B}-{C}{D}-{E}{F}-{H}",
        ),
    }
    invalid = [label for label, (actual, wanted) in expected.items() if actual != wanted]
    if invalid:
        raise RuleConfigError(f"编号规则文件与第一阶段规则不一致：{', '.join(invalid)}")
    return config


@lru_cache
def get_rule_config() -> RuleConfig:
    return load_rule_config(get_settings().rule_file_path)
