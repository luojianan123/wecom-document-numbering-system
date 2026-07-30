from pathlib import Path

import pytest

from app.services.abbreviations import AbbreviationMatch, AbbreviationRegistry
from app.services.ai_names import NameCorrection
from app.services.numbering import NumberingError, NumberingService

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def service() -> NumberingService:
    return NumberingService(AbbreviationRegistry(ROOT / "文件简号.xlsx"))


def test_generates_code_with_stage(service: NumberingService) -> None:
    result = service.generate(
        "控制模块正样件技术要求.docx",
        NameCorrection(
            standard_name="控制模块正样件技术要求",
            component_level="3",
            function_code="KZ",
        ),
        "1234",
    )
    assert result.final_code == "GH1234-3KZ-010JY-Z-2.00"


def test_generates_single_hyphen_when_stage_is_empty(service: NumberingService) -> None:
    result = service.generate(
        "控制模块技术要求.docx",
        NameCorrection(
            standard_name="控制模块技术要求",
            component_level="3",
            function_code="KZ",
        ),
        "1234",
    )
    assert result.final_code == "GH1234-3KZ-010JY-1.00"
    assert "--" not in result.final_code


def test_pcba_is_checked_before_pcb(service: NumberingService) -> None:
    pcba = service.generate(
        "控制PCBA电装投板文件",
        NameCorrection(standard_name="控制PCBA电装投板文件"),
        "1234",
    )
    pcb = service.generate(
        "控制PCB加工要求",
        NameCorrection(standard_name="控制PCB加工要求"),
        "1234",
    )
    assert pcba.segment_c == "5"
    assert pcba.segment_f == "GB2"
    assert pcb.segment_c == "7"
    assert pcb.segment_f == "PB"


@pytest.mark.parametrize(
    "file_name",
    [
        "主控板技术要求",
        "电源板使用说明书",
        "控制板设计报告",
        "接口板测试计划",
        "数据采集板技术要求",
        "FPGA处理板使用说明书",
    ],
)
def test_board_files_default_to_pcba_level_five(
    service: NumberingService,
    file_name: str,
) -> None:
    result = service.generate(
        file_name,
        NameCorrection(
            standard_name=file_name,
            component_level="3",
            function_code="KZ",
        ),
        "1234",
    )

    assert result.segment_c == "5"


@pytest.mark.parametrize(
    "file_name",
    [
        "主控板PCB加工要求",
        "电源板PCB设计文件",
        "接口板PCB检验报告",
    ],
)
def test_explicit_pcb_in_board_name_forces_level_seven(
    service: NumberingService,
    file_name: str,
) -> None:
    result = service.generate(
        file_name,
        NameCorrection(
            standard_name=file_name,
            component_level="5",
            function_code="KZ",
        ),
        "1234",
    )

    assert result.segment_c == "7"


@pytest.mark.parametrize(
    ("file_name", "file_code"),
    [
        ("控制板卡电装要求", "DY"),
        ("控制逻辑图", "LJ"),
        ("控制操作系统镜像文件", "XW"),
    ],
)
def test_level_five_rules_override_ai_candidate(
    service: NumberingService,
    file_name: str,
    file_code: str,
) -> None:
    result = service.generate(
        file_name,
        NameCorrection(
            standard_name=file_name,
            component_level="3",
            function_code="KZ",
        ),
        "1234",
    )

    assert result.segment_c == "5"
    assert result.segment_f == file_code


@pytest.mark.parametrize(
    ("original_name", "standard_name", "file_code"),
    [
        (
            "控制逻辑单元集成测试计划",
            "控制仿真测试计划",
            "UTP",
        ),
        (
            "控制逻辑配置项测试报告",
            "控制确认测试报告",
            "ITR",
        ),
    ],
)
def test_standardized_logic_tests_keep_level_and_software_prefix(
    service: NumberingService,
    original_name: str,
    standard_name: str,
    file_code: str,
) -> None:
    result = service.generate(
        original_name,
        NameCorrection(
            standard_name=standard_name,
            component_level="3",
            function_code="KZ",
        ),
        "1234",
    )

    assert result.standard_name == standard_name
    assert result.segment_c == "5"
    assert result.segment_f == file_code
    assert result.final_code.startswith("R-GH1234-5KZ-")


def test_software_uses_level_five_and_r_prefix(service: NumberingService) -> None:
    software = service.generate(
        "控制模块软件配置管理计划",
        NameCorrection(
            standard_name="控制模块软件配置管理计划",
            component_level="3",
            function_code="KZ",
        ),
        "1234",
    )

    assert software.segment_c == "5"
    assert software.segment_f == "SCP"
    assert software.final_code == "R-GH1234-5KZ-010SCP-1.00"


def test_software_name_forces_r_prefix_for_non_software_abbreviation(
    service: NumberingService,
) -> None:
    software = service.generate(
        "控制软件任务书",
        NameCorrection(
            standard_name="控制软件任务书",
            component_level="3",
            function_code="KZ",
        ),
        "1234",
    )

    assert software.segment_f == "RW"
    assert software.segment_c == "5"
    assert software.final_code == "R-GH1234-5KZ-010RW-1.00"


def test_generates_fallback_abbreviation_when_workbook_has_no_match(
    service: NumberingService,
) -> None:
    generated = service.generate(
        "压缩存储单元主控软件安全性计划",
        NameCorrection(
            standard_name="压缩存储单元主控软件安全性计划",
            function_code="CC",
        ),
        "1234",
    )

    assert len(generated.segment_f) == 2
    assert generated.segment_f.isalpha()
    assert generated.segment_f.isupper()
    assert generated.final_code == (
        f"R-GH1234-5CC-010{generated.segment_f}-1.00"
    )


def test_fallback_abbreviation_skips_an_occupied_final_code(
    service: NumberingService,
) -> None:
    first = service.generate(
        "压缩存储单元主控软件安全性计划",
        NameCorrection(
            standard_name="压缩存储单元主控软件安全性计划",
            function_code="CC",
        ),
        "1234",
    )
    second = service.generate(
        "压缩存储单元主控软件安全性计划",
        NameCorrection(
            standard_name="压缩存储单元主控软件安全性计划",
            function_code="CC",
        ),
        "1234",
        unavailable_final_codes={first.final_code},
    )

    assert second.segment_f != first.segment_f
    assert second.final_code != first.final_code


def test_workbook_abbreviation_collision_uses_fallback_code(
    service: NumberingService,
) -> None:
    occupied = "GH1234-3KZ-010JY-1.00"
    generated = service.generate(
        "控制模块技术要求",
        NameCorrection(
            standard_name="控制模块技术要求",
            function_code="KZ",
        ),
        "1234",
        unavailable_final_codes={occupied},
    )

    assert generated.segment_f != "JY"
    assert generated.final_code != occupied
    assert generated.final_code.startswith("GH1234-3KZ-010")


def test_software_stage_keeps_r_prefix(service: NumberingService) -> None:
    software = service.generate(
        "控制模块软件研制任务书正样件",
        NameCorrection(
            standard_name="控制模块软件研制任务书正样件",
            component_level="3",
            function_code="KZ",
        ),
        "1234",
    )

    assert software.segment_c == "5"
    assert software.segment_f == "SSA"
    assert software.final_code == "R-GH1234-5KZ-010SSA-Z-2.00"


def test_review_conclusion_report_uses_p_prefix(
    service: NumberingService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        service.abbreviations,
        "match",
        lambda _: AbbreviationMatch(
            alias="评审结论报告",
            code="JLB",
        ),
    )

    report = service.generate(
        "控制模块评审结论报告",
        NameCorrection(
            standard_name="控制模块结论文件",
            component_level="3",
            function_code="KZ",
        ),
        "1234",
    )

    assert report.final_code == "P-GH1234-3KZ-010JLB-1.00"


def test_software_review_conclusion_report_keeps_p_first(
    service: NumberingService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        service.abbreviations,
        "match",
        lambda _: AbbreviationMatch(
            alias="软件评审结论报告",
            code="JLB",
            is_software=True,
        ),
    )

    report = service.generate(
        "控制模块软件评审结论报告",
        NameCorrection(
            standard_name="控制模块软件评审结论报告",
            function_code="KZ",
        ),
        "1234",
    )

    assert report.segment_c == "5"
    assert report.final_code == "P-R-GH1234-5KZ-010JLB-1.00"


def test_review_phrase_is_not_treated_as_file_type_when_not_at_end(
    service: NumberingService,
) -> None:
    result = service.generate(
        "控制评审结论报告模板使用说明书",
        NameCorrection(
            standard_name="控制评审结论报告模板使用说明书",
            component_level="3",
            function_code="KZ",
        ),
        "1234",
    )

    assert result.segment_f == "SS"
    assert result.final_code == "GH1234-3KZ-010SS-1.00"


def test_parses_and_validates_manual_code(service: NumberingService) -> None:
    manual = service.parse_manual_code(
        "控制模块未收录软件文件",
        "r-gh1234-5kz-010x1-1.00",
        "1234",
    )

    assert manual.standard_name == "控制模块未收录软件文件"
    assert manual.segment_c == "5"
    assert manual.segment_f == "X1"
    assert manual.final_code == "R-GH1234-5KZ-010X1-1.00"


def test_manual_code_applies_term_mapping_and_known_software_prefix(
    service: NumberingService,
) -> None:
    manual = service.parse_manual_code(
        "控制逻辑单元集成测试计划",
        "R-GH1234-5KZ-010UTP-1.00",
        "1234",
    )

    assert manual.standard_name == "控制仿真测试计划"
    assert manual.segment_c == "5"


def test_manual_code_validates_multi_device_level(
    service: NumberingService,
) -> None:
    manual = service.parse_manual_code(
        "3台计算机组成的通信系统技术要求",
        "GH1234-2TX-010JY-1.00",
        "1234",
    )

    assert manual.segment_c == "2"


def test_parses_manual_review_conclusion_report(
    service: NumberingService,
) -> None:
    manual = service.parse_manual_code(
        "控制模块评审结论报告",
        "p-gh1234-3kz-010x2-1.00",
        "1234",
    )

    assert manual.final_code == "P-GH1234-3KZ-010X2-1.00"


@pytest.mark.parametrize(
    ("file_name", "final_code", "message"),
    [
        (
            "控制模块技术要求",
            "GH5678-3KZ-010JY-1.00",
            "与当前项目",
        ),
        (
            "控制模块正样件技术要求",
            "GH1234-3KZ-010JY-1.00",
            "阶段号或版本号",
        ),
        (
            "控制PCB加工要求",
            "GH1234-5KZ-010PB-1.00",
            "部组件级别应为 7",
        ),
        (
            "控制模块评审结论报告",
            "GH1234-3KZ-010X2-1.00",
            "必须以 P- 开头",
        ),
        (
            "控制模块技术要求",
            "P-GH1234-3KZ-010JY-1.00",
            "仅评审结论报告",
        ),
        (
            "控制逻辑单元集成测试计划",
            "GH1234-5KZ-010UTP-1.00",
            "必须以 R- 开头",
        ),
        (
            "控制模块技术要求",
            "GH1234-2KZ-010JY-1.00",
            "部组件级别应为 3",
        ),
        (
            "一台设备产品技术要求",
            "GH1234-7KZ-010JY-1.00",
            "部组件级别应为 3",
        ),
        (
            "3台计算机组成的通信系统技术要求",
            "GH1234-3TX-010JY-1.00",
            "部组件级别应为 2",
        ),
    ],
)
def test_rejects_invalid_manual_code(
    service: NumberingService,
    file_name: str,
    final_code: str,
    message: str,
) -> None:
    with pytest.raises(NumberingError, match=message):
        service.parse_manual_code(file_name, final_code, "1234")


def test_system_level_and_identification_stage(service: NumberingService) -> None:
    system = service.generate(
        "多设备通信分系统使用说明书鉴定件",
        NameCorrection(standard_name="多设备通信分系统使用说明书鉴定件"),
        "1234",
    )

    assert system.segment_c == "2"
    assert system.segment_g == "C"
    assert system.segment_h == "1.00"
    assert system.final_code == "GH1234-2TX-010SS-C-1.00"


def test_strips_legacy_project_prefix_from_standard_name(
    service: NumberingService,
) -> None:
    result = service.generate(
        "1234控制模块技术要求",
        NameCorrection(standard_name="1234控制模块技术要求"),
        "1234",
    )

    assert result.standard_name == "控制模块技术要求"


def test_rejects_project_mismatch(service: NumberingService) -> None:
    with pytest.raises(NumberingError, match="不一致"):
        service.generate(
            "5678控制模块技术要求",
            NameCorrection(standard_name="5678控制模块技术要求"),
            "1234",
        )
