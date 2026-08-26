import re
import unicodedata

from pypinyin import Style, lazy_pinyin

from ..models import ComponentNode


class ComponentNumberingError(ValueError):
    pass


def machine_abbreviation(name: str) -> str:
    normalized = unicodedata.normalize("NFKC", name).strip()
    if not normalized:
        raise ComponentNumberingError("整机名称不能为空")
    letters: list[str] = []
    for char in normalized:
        if char.isascii() and char.isalpha():
            letters.append(char.upper())
        elif re.fullmatch(r"[\u4e00-\u9fff]", char):
            initial = "".join(
                lazy_pinyin(char, style=Style.FIRST_LETTER, errors="ignore")
            ).upper()
            if re.fullmatch(r"[A-Z]", initial):
                letters.append(initial)
    abbreviation = "".join(letters)[:6]
    if not abbreviation:
        raise ComponentNumberingError("无法从整机名称生成英文首字母缩写")
    return abbreviation


def stage_code(is_prototype: bool) -> str:
    return "Z" if is_prototype else "G"


def version_code(stage: str) -> str:
    return "2.00" if stage == "Z" else "1.00"


def validate_node_code(
    project_code: str,
    node: ComponentNode,
    code: str,
    parent: ComponentNode | None = None,
) -> tuple[str, str, int]:
    """Validate a manually edited code and return normalized code metadata."""
    value = code.strip().upper()
    parts = value.split("-")
    if node.kind == "machine":
        pattern = (
            rf"^GH{re.escape(project_code)}-[A-Z]{{1,6}}-00-"
            rf"(?P<stage>[GZ])-(?P<version>[12]\.00)$"
        )
        sequence = 0
    elif node.kind == "component":
        pattern = (
            rf"^GH{re.escape(project_code)}-[A-Z]{{1,6}}-\d{{2}}-00-"
            rf"(?P<stage>[GZ])-(?P<version>[12]\.00)$"
        )
        sequence = int(parts[2]) if len(parts) == 6 and parts[2].isdigit() else -1
    elif node.kind in {"structure", "hardware", "other"}:
        pattern = (
            rf"^GH{re.escape(project_code)}-[A-Z]{{1,6}}-\d{{2}}-\d{{2}}-"
            rf"(?P<stage>[GZ])-(?P<version>[12]\.00)$"
        )
        sequence = int(parts[3]) if len(parts) == 6 and parts[3].isdigit() else -1
    elif node.kind == "part":
        pattern = (
            rf"^GH{re.escape(project_code)}-[A-Z]{{1,6}}-\d{{2}}-\d{{2}}-\d{{2}}-"
            rf"(?P<stage>[GZ])-(?P<version>[12]\.00)$"
        )
        sequence = int(parts[4]) if len(parts) == 7 and parts[4].isdigit() else -1
    else:
        raise ComponentNumberingError(f"{kind_label(node.kind)}编号规则尚未配置")
    match = re.fullmatch(pattern, value)
    if not match:
        raise ComponentNumberingError(f"{kind_label(node.kind)}编号格式不符合当前层级规则")
    stage = match.group("stage")
    if match.group("version") != version_code(stage):
        raise ComponentNumberingError(
            f"{stage}阶段的版本号必须为{version_code(stage)}"
        )
    if sequence < 0 or sequence > 99:
        raise ComponentNumberingError("序列号必须为00至99")
    if node.kind == "component" and sequence == 0:
        raise ComponentNumberingError("部组件序列号必须从01开始")
    if node.kind == "structure" and sequence == 0:
        raise ComponentNumberingError("结构序列号必须从01开始")
    if node.kind == "hardware" and sequence < 10:
        raise ComponentNumberingError("硬件序列号必须从10开始")
    if node.kind == "other" and sequence < 20:
        raise ComponentNumberingError("其他序列号必须从20开始")
    if parent:
        inherited_length = {
            "component": 2,
            "structure": 3,
            "hardware": 3,
            "other": 3,
            "part": 4,
        }.get(node.kind)
        parent_parts = parent.code.split("-")
        if inherited_length and parts[:inherited_length] != parent_parts[:inherited_length]:
            raise ComponentNumberingError("编号的上级继承段必须与当前上级编号一致")
    return value, stage, sequence


def node_prefix(node: ComponentNode) -> list[str]:
    parts = node.code.split("-")
    suffix_length = 2 if re.fullmatch(r"[12]\.00", parts[-1]) else 1
    if len(parts) <= suffix_length:
        raise ComponentNumberingError("上级编号格式不正确")
    return parts[:-suffix_length]


def rebuild_code_suffix(node: ComponentNode) -> str:
    return "-".join([*node_prefix(node), node.stage, version_code(node.stage)])


def build_machine_code(project_code: str, name: str, stage: str) -> str:
    return f"GH{project_code}-{machine_abbreviation(name)}-00-{stage}-{version_code(stage)}"


def build_child_code(parent: ComponentNode, kind: str, sequence: int, stage: str) -> str:
    prefix = node_prefix(parent)
    if kind == "component" and parent.kind == "machine":
        segments = [prefix[0], prefix[1], f"{sequence:02d}", "00", stage]
        return "-".join([*segments, version_code(stage)])
    if kind in {"structure", "hardware", "other"} and parent.kind == "component":
        segments = [*prefix[:-1], f"{sequence:02d}", stage]
        return "-".join([*segments, version_code(stage)])
    if kind == "part" and parent.kind in {"structure", "hardware"}:
        segments = [*prefix, f"{sequence:02d}", stage]
        return "-".join([*segments, version_code(stage)])
    if kind in {"software", "other"}:
        raise ComponentNumberingError(f"{kind_label(kind)}编号规则尚未配置")
    raise ComponentNumberingError("该层级不能新增所选类型")


def sequence_start(kind: str) -> int:
    return {
        "component": 1,
        "structure": 1,
        "hardware": 10,
        "other": 20,
        "part": 0,
    }.get(kind, 0)


def kind_label(kind: str) -> str:
    return {
        "machine": "整机",
        "component": "部组件",
        "structure": "结构",
        "hardware": "硬件",
        "software": "软件",
        "other": "其他",
        "part": "零件",
    }.get(kind, kind)
