import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher

from .abbreviations import AbbreviationError, AbbreviationRegistry
from .ai_names import normalize_file_name
from .document_rules import standardize_document_terms


class FileNameValidationError(ValueError):
    pass


@dataclass(frozen=True)
class SimilarName:
    standard_name: str
    score: float


URL_PATTERN = re.compile(
    r"(?:https?://|www\.|(?:[a-z0-9-]+\.)+(?:com|cn|net|org|io|gov|edu)\b)",
    re.IGNORECASE,
)
PURE_NUMBER_PATTERN = re.compile(r"^[\d._-]+$")
REPEATED_CHARACTER_PATTERN = re.compile(r"^(.)\1{2,}$", re.DOTALL)
REPEATED_GROUP_PATTERN = re.compile(r"^(.{1,3})\1{2,}$", re.DOTALL)
MEANINGLESS_LATIN_PATTERN = re.compile(
    r"^(?:asdf|qwer|zxcv|test|hello|abc|aaa+|xxx+)\d*$",
    re.IGNORECASE,
)
ALLOWED_PUNCTUATION = set("-_()（）[]【】.")
STAGE_WORDS = (
    "正样件",
    "鉴定件",
    "试验件",
    "初样件",
)
GENERIC_PROJECT_WORDS = (
    "专业设备",
    "项目",
    "产品",
    "文件",
    "文档",
)
DOCUMENT_TYPE_SUFFIXES = tuple(
    sorted(
        (
            "软件配置管理计划",
            "软件质量保证计划",
            "方案设计报告",
            "详细设计说明书",
            "概要设计说明书",
            "需求规格说明书",
            "调试作业指导书",
            "作业指导书",
            "加工工艺要求",
            "外包技术要求",
            "评审结论报告",
            "开发计划",
            "研制计划",
            "测试计划",
            "试验计划",
            "质量计划",
            "技术要求",
            "工艺要求",
            "使用说明书",
            "技术说明书",
            "用户手册",
            "测试细则",
            "测试报告",
            "试验报告",
            "设计报告",
            "分析报告",
            "会议纪要",
            "BOM清单",
            "生产用文件",
            "工程文件",
            "设计文件",
            "源程序",
            "源代码",
            "原理图",
            "大纲",
            "计划",
            "报告",
            "说明书",
            "手册",
            "细则",
            "清单",
            "文件",
        ),
        key=len,
        reverse=True,
    )
)
OBVIOUSLY_UNRELATED_WORDS = (
    "昨晚",
    "昨天",
    "今天吃",
    "好吃",
    "水果",
    "早餐",
    "午饭",
    "晚饭",
    "夜宵",
    "餐厅",
    "菜谱",
    "旅游",
    "购物",
    "电影",
    "音乐",
    "心情",
    "睡觉",
    "天气",
    "讨厌",
    "喜欢吃",
    "想吃",
    "真好吃",
)
PERSONAL_EXPRESSION_PATTERN = re.compile(
    r"(?:^|[^一-龥])?(?:我|我们|你|你们|他|她|他们)"
    r".{0,10}(?:吃|喝|讨厌|喜欢|爱|恨|睡|玩|逛|买|看电影|听歌|心情)"
)
PERSONAL_JUDGEMENT_PATTERN = re.compile(
    r"^[\u4e00-\u9fff]{2,8}(?:是|很|真|太|像)"
    r"(?:猪|狗|笨|傻|蠢|坏|丑|讨厌|恶心|垃圾|废物|混蛋|白痴)"
)
INSULT_WORDS = (
    "是猪",
    "像猪",
    "笨蛋",
    "傻瓜",
    "傻子",
    "蠢货",
    "垃圾",
    "废物",
    "混蛋",
    "白痴",
    "恶心",
)
COMMON_CHINESE_SURNAMES = set(
    "赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华"
    "金魏陶姜戚谢邹喻柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方"
    "俞任袁柳鲍史唐费廉岑薛雷贺倪汤滕殷罗毕郝邬安常乐于时傅皮"
    "卞齐康伍余元卜顾孟平黄穆萧尹姚邵汪祁毛禹狄米贝明臧计伏成"
    "戴谈宋茅庞熊纪舒屈项祝董梁杜阮蓝闵季贾路娄危江童颜郭梅盛"
    "林刁钟徐邱骆高夏蔡田樊胡凌霍虞万支柯管卢莫经房裘缪干解应"
    "宗丁宣邓郁单杭洪包诸左石崔吉龚程嵇邢裴陆荣翁荀羊甄曲封芮"
    "储靳汲邴糜松井段富巫乌焦巴弓牧隗山谷车侯宓蓬全郗班仰秋仲"
    "伊宫宁仇栾暴甘厉戎祖武符刘景詹束龙叶幸司韶郜黎蓟薄印宿怀"
    "蒲台从鄂索咸籍赖卓蔺屠蒙池乔阴胥能苍双闻莘党翟谭贡劳逄姬"
    "申扶堵冉宰郦雍郤璩桑桂濮牛寿通边扈燕冀浦尚农温别庄晏柴瞿"
    "阎充慕连茹习宦艾鱼容向古易慎戈廖庾终暨居衡步都耿满弘匡国"
    "文寇广禄阙东欧利蔚越夔隆师巩厍聂晁勾敖融冷訾辛阚那简饶空"
    "曾毋沙乜养鞠须丰巢关蒯相查后荆红游竺权逯盖益桓公"
)
ENGINEERING_SUBJECT_WORDS = (
    "板",
    "卡",
    "模块",
    "单元",
    "系统",
    "分系统",
    "软件",
    "设备",
    "组件",
    "部件",
    "电路",
    "结构",
    "逻辑",
    "程序",
    "驱动",
    "接口",
    "控制",
    "通信",
    "通讯",
    "存储",
    "处理",
    "计算",
    "网络",
    "数据",
    "导航",
    "感知",
    "任务",
    "电源",
    "机箱",
    "整机",
    "主机",
    "终端",
    "平台",
    "算法",
    "数据库",
    "fpga",
    "pcb",
    "pcba",
)


def normalized_standard_name(value: str) -> str:
    return standardize_document_terms(normalize_file_name(value)).casefold()


def extract_product_subject(
    value: str,
    abbreviations: AbbreviationRegistry,
) -> str:
    subject = standardize_document_terms(normalize_file_name(value))
    subject = re.sub(r"^\d{4}[-_ ]*", "", subject)
    try:
        alias = abbreviations.match(subject).alias
    except AbbreviationError:
        alias = ""
    if alias:
        alias_index = subject.rfind(alias)
        if alias_index >= 0:
            subject = subject[:alias_index] + subject[alias_index + len(alias) :]
    for suffix in DOCUMENT_TYPE_SUFFIXES:
        if subject.endswith(suffix):
            subject = subject[: -len(suffix)]
            break
    for word in (*STAGE_WORDS, *GENERIC_PROJECT_WORDS):
        subject = subject.replace(word, "")
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", subject.casefold())


def is_obviously_unrelated_name(
    candidate: str,
    abbreviations: AbbreviationRegistry,
) -> bool:
    normalized_candidate = normalized_standard_name(candidate)
    if any(word in normalized_candidate for word in OBVIOUSLY_UNRELATED_WORDS):
        return True
    if any(word in normalized_candidate for word in INSULT_WORDS):
        return True
    if PERSONAL_JUDGEMENT_PATTERN.search(normalized_candidate):
        return True

    candidate_subject = extract_product_subject(candidate, abbreviations)
    if len(candidate_subject) < 2:
        return True
    if PERSONAL_EXPRESSION_PATTERN.search(candidate_subject):
        return True
    is_short_chinese_name = (
        2 <= len(candidate_subject) <= 4
        and re.fullmatch(r"[\u4e00-\u9fff]+", candidate_subject) is not None
        and candidate_subject[0] in COMMON_CHINESE_SURNAMES
    )
    has_engineering_subject = any(
        word in candidate_subject for word in ENGINEERING_SUBJECT_WORDS
    )
    return is_short_chinese_name and not has_engineering_subject


def validate_user_file_name(value: str) -> str:
    raw_value = unicodedata.normalize("NFKC", value).strip()
    if URL_PATTERN.search(raw_value):
        raise FileNameValidationError("文件名称不能包含网址")
    normalized = normalize_file_name(value)
    if not normalized:
        raise FileNameValidationError("文件名称不能为空")
    if PURE_NUMBER_PATTERN.fullmatch(normalized):
        raise FileNameValidationError("文件名称不能为纯数字")
    if (
        REPEATED_CHARACTER_PATTERN.fullmatch(normalized)
        or REPEATED_GROUP_PATTERN.fullmatch(normalized)
    ):
        raise FileNameValidationError("文件名称不能使用无意义重复字符")
    if MEANINGLESS_LATIN_PATTERN.fullmatch(normalized):
        raise FileNameValidationError("文件名称与项目文件明显无关")

    meaningful_count = 0
    for character in normalized:
        category = unicodedata.category(character)
        if category.startswith(("L", "N")):
            meaningful_count += 1
            continue
        if character in ALLOWED_PUNCTUATION:
            continue
        if category in {"So", "Sk", "Cs"}:
            raise FileNameValidationError("文件名称不能包含表情")
        raise FileNameValidationError(f"文件名称包含不支持的特殊符号“{character}”")

    if meaningful_count < 2:
        raise FileNameValidationError("文件名称内容过短或缺少有效含义")
    return normalized


def find_similar_names(
    candidate: str,
    existing_names: list[str],
    *,
    limit: int = 5,
) -> list[SimilarName]:
    normalized_candidate = normalized_standard_name(candidate)
    matches: list[SimilarName] = []
    for existing_name in existing_names:
        normalized_existing = normalized_standard_name(existing_name)
        if normalized_existing == normalized_candidate:
            continue
        score = SequenceMatcher(
            None,
            normalized_candidate,
            normalized_existing,
        ).ratio()
        shorter_length = min(
            len(normalized_candidate),
            len(normalized_existing),
        )
        is_contained = (
            shorter_length >= 4
            and (
                normalized_candidate in normalized_existing
                or normalized_existing in normalized_candidate
            )
        )
        if score >= 0.72 or is_contained:
            matches.append(SimilarName(existing_name, round(score, 3)))
    return sorted(matches, key=lambda item: item.score, reverse=True)[:limit]
