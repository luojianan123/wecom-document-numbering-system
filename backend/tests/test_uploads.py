from io import BytesIO

import pytest
from openpyxl import Workbook

from app.services.uploads import MAX_FILE_BYTES, UploadError, parse_file_names


def test_parses_csv_and_deduplicates() -> None:
    content = "文件名称\n1234控制模块技术要求\n1234控制模块技术要求\n".encode()
    assert parse_file_names("list.csv", content) == ["1234控制模块技术要求"]


def test_parses_xlsx() -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["文件名称"])
    sheet.append(["1234控制模块技术要求"])
    buffer = BytesIO()
    workbook.save(buffer)
    assert parse_file_names("list.xlsx", buffer.getvalue()) == ["1234控制模块技术要求"]


def test_rejects_missing_header() -> None:
    with pytest.raises(UploadError, match="文件名称"):
        parse_file_names("list.csv", "名称\nfoo\n".encode())


def test_rejects_file_larger_than_10_mb() -> None:
    with pytest.raises(UploadError, match="10 MB"):
        parse_file_names("list.csv", b"x" * (MAX_FILE_BYTES + 1))
