"""Immutable catalog of product-defined standard profile fields."""

from __future__ import annotations

from collections.abc import Iterable

from resume_agent.profile.models import (
    FieldType,
    PageOption,
    Scope,
    Sensitivity,
    StandardFieldDefinition,
    ValidationRule,
)


def _options(*values: str) -> list[PageOption]:
    return [PageOption(value=value, label=value) for value in values]


def _field(
    field_id: str,
    label: str,
    field_type: FieldType,
    *,
    sensitivity: Sensitivity = Sensitivity.NORMAL,
    confirmation: bool = False,
    scopes: Iterable[Scope] = (Scope.GLOBAL,),
    aliases: Iterable[str] = (),
    options: list[PageOption] | None = None,
    validation: ValidationRule | None = None,
) -> StandardFieldDefinition:
    return StandardFieldDefinition(
        id=field_id,
        label=label,
        field_type=field_type,
        default_sensitivity=sensitivity,
        requires_confirmation=confirmation,
        allowed_scopes=list(scopes),
        aliases=list(aliases) or None,
        options=options,
        validation=validation,
    )


_STANDARD_FIELDS: tuple[StandardFieldDefinition, ...] = (
    _field("person.full_name", "姓名", FieldType.TEXT, aliases=("姓名", "name")),
    _field("person.name_en", "英文名/拼音名", FieldType.TEXT),
    _field(
        "person.gender",
        "性别",
        FieldType.ENUM,
        options=_options("男", "女", "其他", "不便透露"),
    ),
    _field("person.birth_date", "出生日期", FieldType.DATE),
    _field("person.birth_year", "出生年份", FieldType.YEAR),
    _field("person.birth_place", "出生地", FieldType.TEXT),
    _field("person.nationality", "国籍", FieldType.TEXT),
    _field("person.ethnicity", "民族", FieldType.TEXT),
    _field(
        "person.id_number",
        "身份证/证件号码",
        FieldType.TEXT,
        sensitivity=Sensitivity.HIGHLY_SENSITIVE,
        confirmation=True,
    ),
    _field(
        "person.political_status",
        "政治面貌",
        FieldType.TEXT,
        sensitivity=Sensitivity.SENSITIVE,
        confirmation=True,
    ),
    _field(
        "person.military_service",
        "服役情况",
        FieldType.TEXT,
        sensitivity=Sensitivity.SENSITIVE,
        confirmation=True,
    ),
    _field(
        "person.marital_status",
        "婚姻状况",
        FieldType.TEXT,
        sensitivity=Sensitivity.SENSITIVE,
        confirmation=True,
    ),
    _field("contact.phone", "手机号", FieldType.PHONE),
    _field("contact.email", "邮箱", FieldType.EMAIL),
    _field("contact.address", "当前住址", FieldType.TEXT),
    _field(
        "contact.hukou_location",
        "户籍所在地",
        FieldType.TEXT,
        sensitivity=Sensitivity.SENSITIVE,
        confirmation=True,
    ),
    _field(
        "contact.postal_code",
        "邮政编码",
        FieldType.TEXT,
        validation=ValidationRule(format="postal_code", pattern=r"^\d{6}$"),
    ),
    _field("education.school_name", "院校/培养单位", FieldType.TEXT),
    _field("education.college", "学院/系", FieldType.TEXT),
    _field("education.major", "专业", FieldType.TEXT),
    _field("education.degree", "学历/学位", FieldType.TEXT),
    _field("education.education_type", "教育类型", FieldType.TEXT),
    _field("education.start_date", "入学时间", FieldType.DATE),
    _field("education.graduation_date", "毕业时间", FieldType.DATE),
    _field("education.gpa", "绩点", FieldType.NUMBER, validation=ValidationRule(minimum=0)),
    _field("education.rank", "排名或排名比例", FieldType.TEXT),
    _field("education.student_status", "学生状态", FieldType.TEXT),
    _field("experience.organization", "公司/单位/组织", FieldType.TEXT),
    _field("experience.title", "职位/角色", FieldType.TEXT),
    _field("experience.start_date", "开始时间", FieldType.DATE),
    _field("experience.end_date", "结束时间", FieldType.DATE),
    _field("experience.description", "职责描述", FieldType.RICH_TEXT),
    _field("experience.achievements", "成果和量化结果", FieldType.RICH_TEXT),
    _field("experience.location", "经历地点", FieldType.TEXT),
    _field("experience.is_current", "是否正在进行", FieldType.BOOLEAN),
    _field("skills.general", "通用技能", FieldType.MULTIVALUE),
    _field("skills.technical", "技术技能", FieldType.MULTIVALUE),
    _field("skills.programming_languages", "编程语言", FieldType.MULTIVALUE),
    _field("languages.spoken", "语言能力及等级", FieldType.MULTIVALUE),
    _field("certifications", "证书", FieldType.MULTIVALUE),
    _field("awards", "奖项和荣誉", FieldType.MULTIVALUE),
    _field("research.publications", "论文/研究/公开成果", FieldType.MULTIVALUE),
    _field("links.github", "GitHub", FieldType.TEXT, validation=ValidationRule(format="url")),
    _field("links.portfolio", "作品集", FieldType.TEXT, validation=ValidationRule(format="url")),
    _field("links.linkedin", "LinkedIn", FieldType.TEXT, validation=ValidationRule(format="url")),
    _field("links.other", "其他链接", FieldType.MULTIVALUE),
    _field(
        "application.expected_salary",
        "期望薪资",
        FieldType.TEXT,
        scopes=(Scope.APPLICATION,),
    ),
    _field(
        "application.preferred_location",
        "意向工作地点",
        FieldType.TEXT,
        scopes=(Scope.APPLICATION,),
    ),
    _field(
        "application.available_start_date",
        "可入职时间",
        FieldType.DATE,
        scopes=(Scope.APPLICATION,),
    ),
    _field(
        "application.willing_to_relocate",
        "是否接受异地/搬迁",
        FieldType.BOOLEAN,
        scopes=(Scope.APPLICATION,),
    ),
    _field(
        "application.willing_to_travel",
        "是否接受出差",
        FieldType.BOOLEAN,
        scopes=(Scope.APPLICATION,),
    ),
    _field(
        "application.referral_source",
        "获知渠道",
        FieldType.TEXT,
        scopes=(Scope.APPLICATION,),
    ),
    _field(
        "application.other_answer",
        "其他问题答案",
        FieldType.RICH_TEXT,
        scopes=(Scope.APPLICATION,),
    ),
)


def standard_field_definitions() -> tuple[StandardFieldDefinition, ...]:
    """Return deep copies so callers cannot mutate the process-wide catalog."""

    return tuple(field.model_copy(deep=True) for field in _STANDARD_FIELDS)


def standard_field_catalog() -> tuple[StandardFieldDefinition, ...]:
    return standard_field_definitions()


def get_standard_field(field_id: str) -> StandardFieldDefinition | None:
    for definition in _STANDARD_FIELDS:
        if definition.id == field_id:
            return definition.model_copy(deep=True)
    return None


def is_standard_field(field_id: str) -> bool:
    return any(definition.id == field_id for definition in _STANDARD_FIELDS)


__all__ = [
    "get_standard_field",
    "is_standard_field",
    "standard_field_catalog",
    "standard_field_definitions",
]
