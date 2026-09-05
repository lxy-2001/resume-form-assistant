from __future__ import annotations

import re
from datetime import date
from typing import Any

from resume_agent.normalization.models import NormalizationIssue
from resume_agent.profile.models import FieldType

_DATE_RE = re.compile(r"^(\d{4})[-/.年](\d{1,2})(?:[-/.月](\d{1,2})日?)?$")
_PHONE_RE = re.compile(r"^\+?86[- ]?(1[3-9]\d{9})$")
_DEGREE_ALIASES = {
    "本科": "本科",
    "学士": "本科",
    "大学本科": "本科",
    "硕士": "硕士",
    "研究生": "硕士",
    "博士": "博士",
    "博士研究生": "博士",
}


def normalize_value(
    field_type: FieldType | str, value: Any
) -> tuple[Any, float, tuple[NormalizationIssue, ...]]:
    """Normalize only transformations that are deterministic and reversible."""

    try:
        kind = field_type if isinstance(field_type, FieldType) else FieldType(field_type)
    except ValueError:
        return value, 0.0, (NormalizationIssue("UNSUPPORTED_TYPE", "字段类型无法标准化", "error"),)
    if value is None:
        return (
            value,
            0.0,
            (NormalizationIssue("EMPTY_VALUE", "字段没有可处理的值", "error", "人工填写"),),
        )
    if isinstance(value, str):
        cleaned = " ".join(value.strip().split())
    else:
        cleaned = value
    if kind in {FieldType.TEXT, FieldType.RICH_TEXT, FieldType.ENUM, FieldType.MULTIVALUE}:
        normalized = cleaned
        if isinstance(cleaned, str) and kind is FieldType.TEXT and normalized in _DEGREE_ALIASES:
            normalized = _DEGREE_ALIASES[normalized]
        return normalized, 0.99 if normalized == value else 0.96, ()
    if kind is FieldType.EMAIL:
        normalized = str(cleaned).lower()
        if not re.fullmatch(
            r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", normalized
        ):
            return (
                normalized,
                0.0,
                (NormalizationIssue("INVALID_EMAIL", "邮箱格式无法验证", "error", "修改邮箱"),),
            )
        return normalized, 0.99, ()
    if kind is FieldType.PHONE:
        normalized = str(cleaned).replace(" ", "")
        match = _PHONE_RE.fullmatch(normalized)
        normalized = match.group(1) if match else normalized
        if not re.fullmatch(r"1[3-9]\d{9}", normalized):
            return (
                normalized,
                0.0,
                (NormalizationIssue("INVALID_PHONE", "手机号格式无法验证", "error", "修改手机号"),),
            )
        return normalized, 0.99, ()
    if kind is FieldType.DATE:
        match = _DATE_RE.fullmatch(str(cleaned))
        if not match:
            return (
                cleaned,
                0.0,
                (NormalizationIssue("INVALID_DATE", "日期格式无法标准化", "error", "修改日期"),),
            )
        year, month, day = match.groups()
        try:
            if day is None:
                date(int(year), int(month), 1)
            else:
                date(int(year), int(month), int(day))
        except ValueError:
            return (
                cleaned,
                0.0,
                (NormalizationIssue("INVALID_DATE", "日期不存在", "error", "修改日期"),),
            )
        normalized = (
            f"{year}-{int(month):02d}" if day is None else f"{year}-{int(month):02d}-{int(day):02d}"
        )
        return normalized, 0.98, ()
    if kind is FieldType.YEAR:
        if re.fullmatch(r"\d{4}", str(cleaned)):
            return int(cleaned), 0.99, ()
        return (
            cleaned,
            0.0,
            (NormalizationIssue("INVALID_YEAR", "年份格式无法验证", "error", "修改年份"),),
        )
    if kind is FieldType.NUMBER:
        try:
            number = float(str(cleaned).replace(",", ""))
        except ValueError:
            return (
                cleaned,
                0.0,
                (NormalizationIssue("INVALID_NUMBER", "数字格式无法验证", "error", "修改数字"),),
            )
        return number, 0.98, ()
    if kind is FieldType.BOOLEAN:
        if isinstance(cleaned, bool):
            return cleaned, 0.99, ()
        lowered = str(cleaned).lower()
        if lowered in {"是", "yes", "true", "1"}:
            return True, 0.95, ()
        if lowered in {"否", "no", "false", "0"}:
            return False, 0.95, ()
        return (
            cleaned,
            0.0,
            (NormalizationIssue("INVALID_BOOLEAN", "布尔值无法判断", "error", "人工选择"),),
        )
    return cleaned, 0.8, ()
