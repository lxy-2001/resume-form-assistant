"""Storage- and transport-neutral F001 profile domain models."""

from __future__ import annotations

import json
from datetime import datetime
from enum import StrEnum
from typing import Any, ClassVar, TypeVar

from pydantic import BaseModel, Field, root_validator


class FieldType(StrEnum):
    TEXT = "text"
    EMAIL = "email"
    PHONE = "phone"
    DATE = "date"
    YEAR = "year"
    NUMBER = "number"
    BOOLEAN = "boolean"
    ENUM = "enum"
    MULTIVALUE = "multivalue"
    RICH_TEXT = "rich_text"
    OBJECT = "object"


class Scope(StrEnum):
    GLOBAL = "global"
    WEBSITE = "website"
    APPLICATION = "application"


class Sensitivity(StrEnum):
    NORMAL = "normal"
    SENSITIVE = "sensitive"
    HIGHLY_SENSITIVE = "highly_sensitive"


class ProfileRecordType(StrEnum):
    EDUCATION = "education"
    WORK = "work"
    INTERNSHIP = "internship"
    PROJECT = "project"


class SourceKind(StrEnum):
    MANUAL = "manual"
    IMPORT = "import"
    RULE = "rule"
    AGENT = "agent"
    USER_CORRECTION = "user_correction"
    WEBSITE_CONFIG = "website_config"


class Model(BaseModel):
    class Config:
        extra = "forbid"
        allow_population_by_field_name = True
    _json_type: ClassVar[type[Model]]

    def to_dict(self) -> dict[str, Any]:
        return json.loads(self.json(exclude_none=True))

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_json(cls: type[ModelT], payload: str | bytes) -> ModelT:
        return cls.parse_raw(payload)


ModelT = TypeVar("ModelT", bound=Model)


class Source(Model):
    kind: SourceKind
    profile_field_id: str | None = Field(default=None, min_length=1, max_length=128)
    document_ref: str | None = Field(default=None, min_length=1, max_length=128)
    location: str | None = Field(default=None, min_length=1)
    detail: str | None = Field(default=None, min_length=1)


class ValidationRule(Model):
    format: str | None = None
    pattern: str | None = None
    min_length: int | None = Field(default=None, ge=0)
    max_length: int | None = Field(default=None, ge=0)
    minimum: float | None = None
    maximum: float | None = None
    allowed_values: list[Any] | None = None


class PageOption(Model):
    value: Any
    label: str = Field(min_length=1)
    selected: bool | None = None
    disabled: bool | None = None


class FieldDefinition(Model):
    id: str = Field(min_length=1, max_length=128)
    label: str = Field(min_length=1)
    field_type: FieldType
    default_sensitivity: Sensitivity
    requires_confirmation: bool
    is_custom: bool
    allowed_scopes: list[Scope] = Field(min_length=1)
    aliases: list[str] | None = None
    options: list[PageOption] | None = None
    validation: ValidationRule | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @root_validator
    def validate_definition(cls, values: dict[str, Any]) -> dict[str, Any]:
        if values.get("default_sensitivity") != Sensitivity.NORMAL and not values.get("requires_confirmation"):
            raise ValueError("sensitive definitions require confirmation")
        if values.get("is_custom") and (values.get("created_at") is None or values.get("updated_at") is None):
            raise ValueError("custom definitions require creation and update timestamps")
        if values.get("field_type") == FieldType.ENUM and not values.get("options"):
            raise ValueError("enum definitions require options")
        return values


class StandardFieldDefinition(FieldDefinition):
    is_custom: bool = False


class CustomFieldDefinition(FieldDefinition):
    is_custom: bool = True


class FieldValue(Model):
    field_id: str = Field(min_length=1, max_length=128)
    label: str = Field(min_length=1)
    field_type: FieldType
    value: Any
    scope: Scope
    scope_context: str | None = Field(default=None, min_length=1, max_length=128)
    sensitivity: Sensitivity
    requires_confirmation: bool
    confirmed: bool
    source: Source
    updated_at: datetime

    @root_validator
    def validate_value(cls, values: dict[str, Any]) -> dict[str, Any]:
        if values.get("sensitivity") != Sensitivity.NORMAL and not values.get("requires_confirmation"):
            raise ValueError("sensitive values require confirmation")
        if not values.get("confirmed"):
            raise ValueError("persisted field values must be confirmed")
        if values.get("scope") is Scope.GLOBAL and values.get("scope_context") is not None:
            raise ValueError("global values cannot have scope_context")
        if values.get("scope") is not Scope.GLOBAL and not values.get("scope_context"):
            raise ValueError("website/application values require scope_context")
        return values


class RepeatableRecord(Model):
    record_id: str = Field(min_length=1, max_length=128)
    record_type: ProfileRecordType
    position: int = Field(ge=0)
    fields: list[FieldValue]
    confirmed: bool
    created_at: datetime
    updated_at: datetime

    @root_validator
    def validate_record(cls, values: dict[str, Any]) -> dict[str, Any]:
        if values.get("confirmed") and not values.get("fields"):
            raise ValueError("confirmed records require at least one field")
        if values.get("confirmed") is False:
            raise ValueError("persisted records must be confirmed")
        return values


class ProfileSnapshot(Model):
    profile_id: str = Field(min_length=1, max_length=128)
    profile_version: int = Field(ge=0)
    is_empty: bool | None = None
    fields: list[FieldValue]
    records: list[RepeatableRecord]
    field_definitions: list[FieldDefinition]
    created_at: datetime
    updated_at: datetime

    @root_validator
    def validate_empty_state(cls, values: dict[str, Any]) -> dict[str, Any]:
        actual_empty = not values.get("fields") and not values.get("records")
        if values.get("is_empty") is None:
            values["is_empty"] = actual_empty
        elif values.get("is_empty") != actual_empty:
            raise ValueError("is_empty must match whether fields and records are present")
        return values










setattr(Model, 'model_validate', classmethod(lambda cls, obj: cls.parse_obj(obj)))


