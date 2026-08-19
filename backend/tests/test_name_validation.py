from pathlib import Path

from app.services.abbreviations import AbbreviationRegistry
from app.services.name_validation import (
    extract_product_subject,
    find_similar_names,
    function_subject_key,
    is_obviously_unrelated_name,
)

ROOT = Path(__file__).resolve().parents[2]


def test_extracts_product_subject_without_document_type() -> None:
    registry = AbbreviationRegistry(ROOT / "文件简号.xlsx")

    assert (
        extract_product_subject("我昨晚吃了好吃的水果开发计划", registry) == "我昨晚吃了好吃的水果"
    )
    assert extract_product_subject("通信模块使用说明书.docx", registry) == "通信模块"


def test_detects_only_obvious_life_or_personal_expressions() -> None:
    registry = AbbreviationRegistry(ROOT / "文件简号.xlsx")

    assert not is_obviously_unrelated_name(
        "机载任务智能处理机接口板原理图",
        registry,
    )
    assert not is_obviously_unrelated_name(
        "主控板原理图",
        registry,
    )
    assert is_obviously_unrelated_name(
        "我昨晚吃了好吃的水果开发计划",
        registry,
    )
    assert is_obviously_unrelated_name(
        "我讨厌ljp",
        registry,
    )
    assert is_obviously_unrelated_name(
        "李京平是猪",
        registry,
    )
    assert is_obviously_unrelated_name(
        "李京平原理图",
        registry,
    )
    assert not is_obviously_unrelated_name(
        "李萨如图像处理模块原理图",
        registry,
    )


def test_similarity_requires_matching_file_abbreviation_and_subject() -> None:
    registry = AbbreviationRegistry(ROOT / "文件简号.xlsx")

    assert [
        item.standard_name
        for item in find_similar_names(
            "主控板原理图",
            [
                "接口板原理图",
                "主控板装配图",
                "备用主控板原理图",
            ],
            registry,
        )
    ] == [
        "备用主控板原理图",
    ]

    assert (
        find_similar_names(
            "主控软件测试报告",
            ["主控软件测试计划", "主控软件源代码"],
            registry,
        )
        == []
    )


def test_similarity_skips_names_without_a_known_file_abbreviation() -> None:
    registry = AbbreviationRegistry(ROOT / "文件简号.xlsx")

    assert find_similar_names("主控板临时材料", ["接口板临时材料"], registry) == []


def test_function_subject_key_keeps_software_boards_and_products_separate() -> None:
    registry = AbbreviationRegistry(ROOT / "文件简号.xlsx")

    assert function_subject_key("猎鹰软件测试报告", registry) == "software:猎鹰"
    assert function_subject_key("猎鹰软件使用说明书", registry) == "software:猎鹰"
    assert function_subject_key("飞鹰主控板测试报告", registry) == "board:飞鹰主控"
    assert function_subject_key("飞鹰主控板使用说明书", registry) == "board:飞鹰主控"
    assert function_subject_key("飞鹰产品测试报告", registry) == "product:飞鹰"
