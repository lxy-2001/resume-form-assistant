"""Storage- and transport-neutral F001 profile domain models."""

from __future__ import annotations

import json
import re
from datetime import datetime
from enum import StrEnum
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

CONTRACT_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"
_CONTRACT_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]*\Z")
MAX_CONTRACT_ID_LENGTH = 128


def is_contract_id(value: object) -> bool:
    """Return whether a value satisfies the shared v0.1 Id contract."""

    return (
        isinstance(value, str)
        and len(value) <= MAX_CONTRACT_ID_LENGTH
        and _CONTRACT_ID_RE.fullmatch(value) is not None
    )


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
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    def to_dict(self) -> dict[str, Any]:
        return json.loads(self.model_dump_json(exclude_none=True))

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_json(cls, payload: str | bytes) -> Self:
        return cls.model_validate_json(payload)


class Source(Model):
    kind: SourceKind
    profile_field_id: str | None = Field(
        default=None, min_length=1, max_length=128, pattern=CONTRACT_ID_PATTERN
    )
    document_ref: str | None = Field(
        default=None, min_length=1, max_length=128, pattern=CONTRACT_ID_PATTERN
    )
    location: str | None = Field(default=None, min_length=1)
    detail: str | None = Field(default=None, min_length=1)


class ValidationRule(Model):
    format: Literal["email", "phone", "date", "year", "url", "postal_code"] | None = None
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
    id: str = Field(min_length=1, max_length=128, pattern=CONTRACT_ID_PATTERN)
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

    @model_validator(mode="after")
    def validate_definition(self) -> FieldDefinition:
        if self.default_sensitivity != Sensitivity.NORMAL and not self.requires_confirmation:
            raise ValueError("sensitive definitions require confirmation")
        if self.is_custom:
            if self.created_at is None or self.updated_at is None:
                raise ValueError("custom definitions require creation and update timestamps")
            if not re.fullmatch(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$", self.id):
                raise ValueError("custom definition id has invalid format")
            if not self.label.strip():
                raise ValueError("custom definition label cannot be blank")
            allowed = {
                FieldType.TEXT,
                FieldType.DATE,
                FieldType.NUMBER,
                FieldType.BOOLEAN,
                FieldType.ENUM,
                FieldType.MULTIVALUE,
            }
            if self.field_type not in allowed:
                raise ValueError("custom definition field type is unsupported")
            if self.field_type in {FieldType.ENUM, FieldType.MULTIVALUE} and not self.options:
                raise ValueError("enum and multivalue definitions require options")
            if self.options:
                values = [option.value for option in self.options]
                if len({repr(value) for value in values}) != len(values):
                    raise ValueError("custom definition options must be unique")
        elif self.field_type == FieldType.ENUM and not self.options:
            raise ValueError("enum definitions require options")
        return self


class StandardFieldDefinition(FieldDefinition):
    is_custom: Literal[False] = False


class CustomFieldDefinition(FieldDefinition):
    is_custom: Literal[True] = True


class FieldValue(Model):
    @model_validator(mode="before")
    @classmethod
    def accept_field_id(cls, data: Any) -> Any:
        if isinstance(data, dict) and "field_id" in data:
            data = dict(data)
            data.setdefault("id", data["field_id"])
            data.pop("field_id")
        return data

    id: str = Field(min_length=1, max_length=128, pattern=CONTRACT_ID_PATTERN)
    label: str = Field(min_length=1)
    field_type: FieldType
    value: Any
    scope: Scope
    scope_context: str | None = Field(
        default=None, min_length=1, max_length=128, pattern=CONTRACT_ID_PATTERN
    )
    sensitivity: Sensitivity
    requires_confirmation: bool
    confirmed: bool
    source: Source
    updated_at: datetime
    is_custom: bool = False
    aliases: list[str] | None = None
    options: list[PageOption] | None = None
    validation: ValidationRule | None = None

    @property
    def field_id(self) -> str:
        return self.id

    @model_validator(mode="after")
    def validate_value(self) -> FieldValue:
        if self.sensitivity != Sensitivity.NORMAL and not self.requires_confirmation:
            raise ValueError("sensitive values require confirmation")
        if not self.confirmed:
            raise ValueError("persisted field values must be confirmed")
        if self.scope is Scope.GLOBAL and self.scope_context is not None:
            raise ValueError("global values cannot have scope_context")
        if self.scope is not Scope.GLOBAL and not self.scope_context:
            raise ValueError("website/application values require scope_context")
        return self


class RepeatableRecord(Model):
    record_id: str = Field(min_length=1, max_length=128, pattern=CONTRACT_ID_PATTERN)
    record_type: ProfileRecordType
    position: int = Field(strict=True, ge=0)
    fields: list[FieldValue]
    confirmed: bool
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def validate_record(self) -> RepeatableRecord:
        if self.confirmed and not self.fields:
            raise ValueError("confirmed records require at least one field")
        if self.confirmed is False:
            raise ValueError("persisted records must be confirmed")
        return self


class ProfileSnapshot(Model):
    profile_id: str = Field(min_length=1, max_length=128, pattern=CONTRACT_ID_PATTERN)
    profile_version: int = Field(strict=True, ge=0)
    is_empty: bool | None = None
    fields: list[FieldValue]
    records: list[RepeatableRecord]
    field_definitions: list[StandardFieldDefinition | CustomFieldDefinition]
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def validate_empty_state(self) -> ProfileSnapshot:
        actual_empty = not self.fields and not self.records
        if self.is_empty is None:
            object.__setattr__(self, "is_empty", actual_empty)
        elif self.is_empty != actual_empty:
            raise ValueError("is_empty must match whether fields and records are present")
        return self
