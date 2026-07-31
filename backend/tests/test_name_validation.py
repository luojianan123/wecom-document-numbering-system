from pathlib import Path

from app.services.abbreviations import AbbreviationRegistry
from app.services.name_validation import (
    extract_product_subject,
    is_obviously_unrelated_name,
)

ROOT = Path(__file__).resolve().parents[2]


def test_extracts_product_subject_without_document_type() -> None:
    registry = AbbreviationRegistry(ROOT / "文件简号.xlsx")

    assert (
        extract_product_subject("我昨晚吃了好吃的水果开发计划", registry)
        == "我昨晚吃了好吃的水果"
    )
    assert (
        extract_product_subject("通信模块使用说明书.docx", registry)
        == "通信模块"
    )


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
