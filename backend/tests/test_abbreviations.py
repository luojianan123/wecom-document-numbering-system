from pathlib import Path

import pytest
from openpyxl import Workbook

from app.services.abbreviations import AbbreviationError, AbbreviationRegistry

ROOT = Path(__file__).resolve().parents[2]


def test_loads_real_abbreviation_workbook() -> None:
    registry = AbbreviationRegistry(ROOT / "文件简号.xlsx")
    assert registry.entry_count >= 120


def test_prefers_longest_specific_alias() -> None:
    registry = AbbreviationRegistry(ROOT / "文件简号.xlsx")
    assert registry.match("1234控制模块调试作业指导书").code == "TS"
    assert registry.match("1234控制模块作业指导书").code == "TS"


@pytest.mark.parametrize(
    ("suffix", "expected_code"),
    [
        ("开发计划", "SDP"),
        ("质量保证计划", "SQA"),
        ("质量保证大纲", "SQA"),
        ("质保计划", "SQA"),
        ("质保大纲", "SQA"),
        ("配置管理计划", "SCP"),
        ("调试记录", "TJ"),
        ("调试作业指导书", "TS"),
        ("调试指导书", "TS"),
        ("作业指导书", "TS"),
        ("技术状态管理计划", "CP"),
    ],
)
def test_fixed_suffix_abbreviations_override_workbook_matches(
    suffix: str,
    expected_code: str,
) -> None:
    registry = AbbreviationRegistry(ROOT / "文件简号.xlsx")

    matched = registry.match(f"火星地物高光谱成像仪{suffix}")

    assert matched.code == expected_code
    assert matched.alias == suffix


def test_handles_merged_cells_and_shared_suffixes() -> None:
    registry = AbbreviationRegistry(ROOT / "文件简号.xlsx")
    assert registry.match("1234电子设备制作文件").code == "ZZ"
    assert registry.match("1234电路板组件装联工艺要求").code == "ZL"
    assert registry.match("1234组件装联文件").code == "ZL"


def test_uses_codes_directly_from_workbook() -> None:
    registry = AbbreviationRegistry(ROOT / "文件简号.xlsx")
    software_match = registry.match("1234软件配置管理计划")
    assert software_match.code == "SCP"
    assert software_match.is_software is True
    assert registry.match("1234软件概要设计说明").code == "PDD"
    assert registry.match("1234软件详细设计说明").code == "DDD"
    assert registry.match("1234软件单元测试计划").code == "UTP"
    assert registry.match("1234软件集成测试计划").code == "UTP"
    unit_report = registry.match("1234软件单元测试报告")
    integration_report = registry.match("1234软件集成测试报告")
    assert (unit_report.code, unit_report.is_software) == ("UTR", True)
    assert (integration_report.code, integration_report.is_software) == (
        "UTR",
        True,
    )
    assert registry.match("1234软件源程序").code == "SP"
    assert registry.match("1234软件源代码").code == "SP"


def test_software_classification_comes_from_the_workbook_marker() -> None:
    registry = AbbreviationRegistry(ROOT / "文件简号.xlsx")
    assert registry.match("1234技术要求").is_software is False
    assert registry.match("1234测试软件").is_software is False
    assert registry.match("1234数据库设计说明").is_software is True


def test_matches_standardized_logic_test_terms_to_workbook_rules() -> None:
    registry = AbbreviationRegistry(ROOT / "文件简号.xlsx")
    simulation = registry.match("1234控制仿真测试计划")
    confirmation = registry.match("1234控制确认测试报告")

    assert (simulation.code, simulation.is_software) == ("UTP", True)
    assert (confirmation.code, confirmation.is_software) == ("ITR", True)


def test_requires_explicit_software_marker(tmp_path: Path) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["文件名称", "文件简号"])
    sheet.append(["软件研制任务书", "SSA"])
    source = tmp_path / "文件简号.xlsx"
    workbook.save(source)
    workbook.close()

    with pytest.raises(AbbreviationError, match="以下为软件"):
        AbbreviationRegistry(source)
