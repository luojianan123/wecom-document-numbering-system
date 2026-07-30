from pathlib import Path

import pytest

from app.services.rule_config import RuleConfigError, load_rule_config

ROOT = Path(__file__).resolve().parents[2]


def test_loads_project_rule_file() -> None:
    config = load_rule_config(ROOT / "编号规则采集模板.yaml")

    assert config.version == "V1.1"
    assert config.segment_a == "GH"
    assert config.segment_e == "010"
    assert config.without_stage_format == "{A}{B}-{C}{D}-{E}{F}-{H}"


def test_rejects_invalid_without_stage_format(tmp_path: Path) -> None:
    rule_file = tmp_path / "rules.yaml"
    rule_file.write_text(
        """
rule: {name: test, version: V1}
segments:
  A: {value: GH}
  E: {value: "010"}
format:
  with_stage: "{A}{B}-{C}{D}-{E}{F}-{G}-{H}"
  without_stage: "{A}{B}-{C}{D}-{E}{F}--{H}"
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(RuleConfigError, match="无阶段号格式"):
        load_rule_config(rule_file)
