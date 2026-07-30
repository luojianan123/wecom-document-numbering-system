import hashlib
import itertools
import random
import re
import unicodedata
from collections.abc import Collection
from dataclasses import dataclass

from pypinyin import Style, lazy_pinyin

from .abbreviations import (
    AbbreviationError,
    AbbreviationMatch,
    AbbreviationRegistry,
)
from .ai_names import NameCorrection, normalize_file_name
from .document_rules import (
    determine_component_level,
    standardize_document_terms,
)
from .rule_config import get_rule_config


class NumberingError(ValueError):
    pass


@dataclass(frozen=True)
class GeneratedNumber:
    original_name: str
    standard_name: str
    segment_a: str
    segment_b: str
    segment_c: str
    segment_d: str
    segment_e: str
    segment_f: str
    segment_g: str
    segment_h: str
    final_code: str


FUNCTION_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("电源", "DY"),
    ("供电", "DY"),
    ("控制", "KZ"),
    ("通信", "TX"),
    ("通讯", "TX"),
    ("显示", "XS"),
    ("测试", "CS"),
    ("试验", "SY"),
    ("检验", "JY"),
    ("数据", "SJ"),
    ("导航", "DH"),
    ("监控", "JK"),
    ("监测", "JC"),
    ("计算", "JS"),
    ("存储", "CC"),
    ("接口", "JK"),
    ("逻辑", "LJ"),
    ("软件", "RJ"),
    ("电路板", "DL"),
)

MANUAL_CODE_PATTERN = re.compile(
    r"^(?P<P>P-)?(?P<R>R-)?GH(?P<B>\d{4})-"
    r"(?P<C>[2357])(?P<D>[A-Z]{2})-"
    r"010(?P<F>[A-Z0-9]{1,12})"
    r"(?:-(?P<G>[ZC]))?-(?P<H>1\.00|2\.00)$"
)
REVIEW_CONCLUSION_REPORT = "评审结论报告"


class NumberingService:
    def __init__(self, abbreviations: AbbreviationRegistry):
        self.abbreviations = abbreviations

    def generate(
        self,
        original_name: str,
        correction: NameCorrection,
        expected_project_code: str | None = None,
        unavailable_final_codes: Collection[str] = (),
    ) -> GeneratedNumber:
        standard_name = standardize_document_terms(
            unicodedata.normalize("NFKC", correction.standard_name).strip()
        )
        project_match = re.match(r"^(\d{4})", standard_name)
        if project_match:
            project_code = project_match.group(1)
            if expected_project_code and project_code != expected_project_code:
                raise NumberingError(
                    f"文件名称项目号 {project_code} 与当前项目 {expected_project_code} 不一致"
                )
            standard_name = standard_name[4:].lstrip("-_ ")
            if not standard_name:
                raise NumberingError("文件名称不能只有项目号")
        elif expected_project_code:
            project_code = expected_project_code
        else:
            raise NumberingError("缺少当前项目号，无法生成编号 B 段")

        source_name = normalize_file_name(original_name)
        matched_abbreviation: AbbreviationMatch | None = None
        try:
            matched_abbreviation = self.abbreviations.match(standard_name)
        except AbbreviationError:
            pass

        if matched_abbreviation is not None:
            generated = self._build_number(
                original_name=original_name,
                source_name=source_name,
                standard_name=standard_name,
                project_code=project_code,
                correction=correction,
                abbreviation=matched_abbreviation,
            )
            if generated.final_code not in unavailable_final_codes:
                return generated

        fallback_abbreviations = self._fallback_abbreviation_candidates(
            standard_name
        )
        for abbreviation in fallback_abbreviations:
            generated = self._build_number(
                original_name=original_name,
                source_name=source_name,
                standard_name=standard_name,
                project_code=project_code,
                correction=correction,
                abbreviation=abbreviation,
            )
            if generated.final_code not in unavailable_final_codes:
                return generated

        if not fallback_abbreviations:
            raise NumberingError("无法从文件名称生成两位备用文件简号")
        raise NumberingError("文件名称可生成的两位备用文件简号均已被占用")

    def _build_number(
        self,
        *,
        original_name: str,
        source_name: str,
        standard_name: str,
        project_code: str,
        correction: NameCorrection,
        abbreviation: AbbreviationMatch,
    ) -> GeneratedNumber:
        is_software = (
            "软件" in standard_name
            or "软件" in source_name
            or abbreviation.is_software
        )
        component_level = self._component_level(
            f"{standard_name}{source_name}",
            correction.component_level,
            is_software,
        )
        function_code = self._function_code(
            standard_name,
            correction.function_code,
            abbreviation.alias,
        )
        stage, version = self._stage_and_version(standard_name)
        rule = get_rule_config()

        segment_a = rule.segment_a
        segment_e = rule.segment_e
        values = {
            "A": segment_a,
            "B": project_code,
            "C": component_level,
            "D": function_code,
            "E": segment_e,
            "F": abbreviation.code,
            "G": stage,
            "H": version,
        }
        base_code = (
            rule.with_stage_format if stage else rule.without_stage_format
        ).format(**values)
        prefixes: list[str] = []
        if (
            self._is_review_conclusion_report(standard_name)
            or self._is_review_conclusion_report(source_name)
        ):
            prefixes.append("P")
        if is_software:
            prefixes.append("R")
        final_code = "-".join([*prefixes, base_code])

        return GeneratedNumber(
            original_name=original_name,
            standard_name=standard_name,
            segment_a=segment_a,
            segment_b=project_code,
            segment_c=component_level,
            segment_d=function_code,
            segment_e=segment_e,
            segment_f=abbreviation.code,
            segment_g=stage,
            segment_h=version,
            final_code=final_code,
        )

    @staticmethod
    def _fallback_abbreviation_candidates(
        file_name: str,
    ) -> tuple[AbbreviationMatch, ...]:
        chinese_chars = re.findall(r"[\u4e00-\u9fff]", file_name)
        pairs = list(itertools.combinations(range(len(chinese_chars)), 2))
        seed = int.from_bytes(
            hashlib.sha256(file_name.encode("utf-8")).digest()[:8],
            "big",
        )
        random.Random(seed).shuffle(pairs)

        candidates: list[AbbreviationMatch] = []
        seen_codes: set[str] = set()
        for first, second in pairs:
            alias = chinese_chars[first] + chinese_chars[second]
            code = "".join(
                lazy_pinyin(
                    alias,
                    style=Style.FIRST_LETTER,
                    errors="ignore",
                )
            ).upper()
            code = re.sub(r"[^A-Z]", "", code)
            if len(code) != 2 or code in seen_codes:
                continue
            seen_codes.add(code)
            candidates.append(AbbreviationMatch(alias=alias, code=code))
        return tuple(candidates)

    def parse_manual_code(
        self,
        original_name: str,
        final_code: str,
        expected_project_code: str,
    ) -> GeneratedNumber:
        source_name = normalize_file_name(original_name)
        standard_name = standardize_document_terms(source_name)
        if not source_name:
            raise NumberingError("文件名称不能为空")
        if re.match(r"^\d{4}", source_name):
            raise NumberingError("文件名称前不要填写项目号")

        normalized_code = unicodedata.normalize("NFKC", final_code).strip().upper()
        match = MANUAL_CODE_PATTERN.fullmatch(normalized_code)
        if not match:
            raise NumberingError(
                "完整编号格式不正确，例如 GH1234-3KZ-010JY-1.00 "
                "或 R-GH1234-5KZ-010SCP-1.00"
            )

        values = match.groupdict(default="")
        if values["B"] != expected_project_code:
            raise NumberingError(
                f"完整编号项目号 {values['B']} 与当前项目 "
                f"{expected_project_code} 不一致"
            )

        is_review_conclusion_report = self._is_review_conclusion_report(
            standard_name
        )
        if is_review_conclusion_report and not values["P"]:
            raise NumberingError("评审结论报告的完整编号必须以 P- 开头")
        if values["P"] and not is_review_conclusion_report:
            raise NumberingError("仅评审结论报告的完整编号可以使用 P- 前缀")

        try:
            abbreviation = self.abbreviations.match(standard_name)
        except AbbreviationError:
            abbreviation = None
        is_software = (
            "软件" in standard_name
            or "软件" in source_name
            or bool(abbreviation and abbreviation.is_software)
        )
        if is_software and not values["R"]:
            raise NumberingError("文件名称含“软件”或属于软件简号范围，必须以 R- 开头")
        if not is_software and values["R"]:
            raise NumberingError("该文件不属于软件文件，不能使用 R- 前缀")

        expected_stage, expected_version = self._stage_and_version(standard_name)
        if values["G"] != expected_stage or values["H"] != expected_version:
            raise NumberingError("完整编号的阶段号或版本号与文件名称不一致")

        expected_level = self._component_level(
            f"{standard_name}{source_name}",
            None,
            is_software=bool(values["R"]),
        )
        if values["C"] != expected_level:
            raise NumberingError(
                f"完整编号的部组件级别应为 {expected_level}"
            )

        return GeneratedNumber(
            original_name=original_name,
            standard_name=standard_name,
            segment_a="GH",
            segment_b=values["B"],
            segment_c=values["C"],
            segment_d=values["D"],
            segment_e="010",
            segment_f=values["F"],
            segment_g=values["G"],
            segment_h=values["H"],
            final_code=normalized_code,
        )

    @staticmethod
    def _is_review_conclusion_report(file_name: str) -> bool:
        normalized = normalize_file_name(file_name)
        normalized = re.sub(r"(?:正样件|鉴定件)$", "", normalized)
        return normalized.endswith(REVIEW_CONCLUSION_REPORT)

    @staticmethod
    def _component_level(
        file_name: str,
        candidate: str | None,
        is_software: bool = False,
    ) -> str:
        return determine_component_level(file_name, candidate, is_software)

    @staticmethod
    def _function_code(
        file_name: str,
        candidate: str | None,
        abbreviation_alias: str,
    ) -> str:
        if candidate and re.fullmatch(r"[A-Z]{2}", candidate.upper()):
            return candidate.upper()

        working = file_name
        working = re.sub(r"^\d{4}", "", working)
        working = working.replace(abbreviation_alias, "")
        for keyword in ("正样件", "鉴定件", "模块", "设备", "产品"):
            working = working.replace(keyword, "")

        for keyword, code in FUNCTION_KEYWORDS:
            if keyword in working:
                return code

        ascii_groups = re.findall(r"[A-Za-z]+", working)
        if ascii_groups:
            letters = "".join(ascii_groups).upper()
            return letters[:2].ljust(2, "X")

        initials = "".join(
            lazy_pinyin(
                working,
                style=Style.FIRST_LETTER,
                errors="ignore",
            )
        ).upper()
        initials = re.sub(r"[^A-Z]", "", initials)
        if not initials:
            raise NumberingError("无法从文件名称确定两位功能代码")
        return initials[:2].ljust(2, "X")

    @staticmethod
    def _stage_and_version(file_name: str) -> tuple[str, str]:
        if "正样件" in file_name:
            return "Z", "2.00"
        if "鉴定件" in file_name:
            return "C", "1.00"
        return "", "1.00"
