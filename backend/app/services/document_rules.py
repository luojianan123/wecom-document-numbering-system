import re
import unicodedata

TERM_MAPPINGS: tuple[tuple[str, str], ...] = (
    ("逻辑单元集成测试", "仿真测试"),
    ("逻辑配置项测试", "确认测试"),
)

ABBREVIATION_EQUIVALENTS: tuple[tuple[str, str], ...] = (
    ("仿真测试", "软件单元/集成测试"),
    ("确认测试", "软件配置项测试"),
)

LEVEL_FIVE_KEYWORDS = (
    "软件",
    "逻辑",
    "操作系统",
    "仿真测试",
    "确认测试",
)

BOARD_ASSEMBLY_KEYWORDS = (
    "板卡",
    "主控板",
    "控制板",
    "电源板",
    "接口板",
    "通信板",
    "通讯板",
    "显示板",
    "采集板",
    "处理板",
    "转接板",
    "扩展板",
    "核心板",
    "母板",
    "子板",
    "底板",
    "背板",
    "载板",
    "驱动板",
    "保护板",
    "滤波板",
    "时钟板",
    "信号板",
    "计算板",
    "存储板",
    "监控板",
    "检测板",
    "测试板",
    "电路板组件",
    "印制板组件",
    "组件装联",
    "电装",
)

BOARD_ASSEMBLY_PATTERN = re.compile(
    r"(?:I/O|IO|CPU|DSP|FPGA|主控|控制|电源|接口|通信|通讯|显示|采集|"
    r"处理|转接|扩展|核心|驱动|保护|滤波|时钟|信号|计算|存储|监控|"
    r"检测|测试|功能|业务|数据|网络|视频|音频|导航|伺服|配电)板",
    re.IGNORECASE,
)

SYSTEM_LEVEL_KEYWORDS = (
    "分系统",
    "系统级",
    "多设备",
    "多计算机",
    "多机",
)

DEVICE_COUNT_PATTERN = re.compile(
    r"(?P<count>\d+|[零〇一二两三四五六七八九十百千]+)"
    r"(?:台|套|部|个)?(?:及以上)?"
    r"[^，。；;]{0,20}?(?:计算机|设备)"
)

MULTI_DEVICE_WORD_PATTERN = re.compile(
    r"(?:多(?:台|套|部|个)?[^，。；;]{0,20}?(?:计算机|设备)|多机)"
)

CHINESE_DIGITS = {
    "零": 0,
    "〇": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}

CHINESE_UNITS = {
    "十": 10,
    "百": 100,
    "千": 1000,
}


def _parse_device_count(value: str) -> int:
    if value.isdigit():
        return int(value)

    total = 0
    digit = 0
    for char in value:
        if char in CHINESE_DIGITS:
            digit = CHINESE_DIGITS[char]
            continue
        unit = CHINESE_UNITS[char]
        total += (digit or 1) * unit
        digit = 0
    return total + digit


def _device_counts(value: str) -> tuple[int, ...]:
    return tuple(
        _parse_device_count(match.group("count")) for match in DEVICE_COUNT_PATTERN.finditer(value)
    )


def standardize_document_terms(value: str) -> str:
    for source, standard in TERM_MAPPINGS:
        value = value.replace(source, standard)
    return value


def abbreviation_match_names(value: str) -> tuple[str, ...]:
    source_equivalent = value
    for standard, source in ABBREVIATION_EQUIVALENTS:
        source_equivalent = source_equivalent.replace(standard, source)
    if source_equivalent == value:
        return (value,)
    return value, source_equivalent


def determine_component_level(
    file_name: str,
    candidate: str | None = None,
    is_software: bool = False,
) -> str:
    normalized = unicodedata.normalize("NFKC", file_name)
    upper = normalized.upper()

    if is_software or "PCBA" in upper:
        return "5"
    if "PCB" in upper:
        return "7"
    if any(keyword in normalized for keyword in LEVEL_FIVE_KEYWORDS):
        return "5"
    if any(
        keyword in normalized for keyword in BOARD_ASSEMBLY_KEYWORDS
    ) or BOARD_ASSEMBLY_PATTERN.search(normalized):
        return "5"

    device_counts = _device_counts(normalized)
    has_system_context = "系统" in normalized
    if has_system_context and (
        any(count >= 2 for count in device_counts) or MULTI_DEVICE_WORD_PATTERN.search(normalized)
    ):
        return "2"

    # An explicit device count without a system context does not establish a
    # multi-device system. A single-device description also takes precedence
    # over a generic phrase such as “系统级”.
    if device_counts:
        return "3"
    if any(keyword in normalized for keyword in SYSTEM_LEVEL_KEYWORDS):
        return "2"
    if candidate in {"2", "3", "5", "7"}:
        return candidate
    return "3"
