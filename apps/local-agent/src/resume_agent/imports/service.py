"""Candidate generation and confirmation for F002 document imports."""

from __future__ import annotations

import re
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from resume_agent.parsing.pipeline import ParsedDocument
from resume_agent.profile.models import FieldType, Scope, Sensitivity, SourceKind
from resume_agent.profile.service import ProfileService
from resume_agent.profile.standard_fields import get_standard_field

_EMAIL_RE = re.compile(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)")
_NAME_RE = re.compile(r"(?:姓名|name)\s*[:：]\s*([^\s,，;；]{1,40})", re.IGNORECASE)
_DATE_RE = re.compile(
    r"(?P<label>出生日期|入学时间|毕业时间|开始时间|结束时间)\s*[:：]?\s*"
    r"(?P<value>\d{4}[-/.年]\d{1,2}[-/.月]\d{1,2}日?)"
)
_ID_RE = re.compile(r"(?<!\d)(?:\d{17}[\dXx]|\d{15})(?!\d)")


@dataclass(frozen=True, slots=True)
class ImportTask:
    task_id: str
    document: ParsedDocument
    candidates: tuple[dict[str, Any], ...]
    created_at: datetime
    profile_version: int


class ImportService:
    """Keep import previews in memory until explicit confirmation."""

    def __init__(
        self, profile_service: ProfileService, *, task_ttl: timedelta = timedelta(minutes=15)
    ) -> None:
        self._profiles = profile_service
        self._tasks: dict[str, ImportTask] = {}
        self._task_ttl = task_ttl

    def _task(self, task_id: str) -> ImportTask:
        task = self._tasks.get(task_id)
        if task is None:
            raise ValueError("import task is unavailable")
        if datetime.now(UTC) - task.created_at > self._task_ttl:
            self._tasks.pop(task_id, None)
            raise ValueError("import task has expired")
        return task

    @staticmethod
    def _candidate(
        *,
        task_id: str,
        document_id: str,
        field_id: str,
        field_type: FieldType,
        value: Any,
        location: str,
        evidence: str,
        confidence: float,
        label: str,
        sensitivity: Sensitivity = Sensitivity.NORMAL,
        existing_value: Any | None = None,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {
            "candidate_id": f"{task_id}-{field_id.replace('.', '-')}",
            "field_id": field_id,
            "label": label,
            "field_type": field_type.value,
            "value": value,
            "source": {
                "kind": SourceKind.IMPORT.value,
                "document_ref": document_id,
                "location": location,
            },
            "confidence": confidence,
            "requires_confirmation": True,
            "sensitivity": sensitivity.value,
            "existing_value_conflict": existing_value is not None and existing_value != value,
            "evidence": [evidence[:240]],
            "warnings": [],
        }
        if existing_value is not None and existing_value != value:
            result["existing_value"] = existing_value
        return result

    def _candidates(
        self, task_id: str, document: ParsedDocument, existing: Mapping[str, Any]
    ) -> tuple[dict[str, Any], ...]:
        result: list[dict[str, Any]] = []
        for segment in document.segments:
            email = _EMAIL_RE.search(segment.text)
            if email:
                definition = get_standard_field("contact.email")
                result.append(
                    self._candidate(
                        task_id=task_id,
                        document_id=document.document_id,
                        field_id="contact.email",
                        field_type=FieldType.EMAIL,
                        value=email.group(0),
                        location=segment.location,
                        evidence=segment.text,
                        confidence=0.96,
                        label=definition.label if definition else "邮箱",
                        existing_value=existing.get("contact.email"),
                    )
                )
            phone = _PHONE_RE.search(segment.text)
            if phone:
                definition = get_standard_field("contact.phone")
                result.append(
                    self._candidate(
                        task_id=task_id,
                        document_id=document.document_id,
                        field_id="contact.phone",
                        field_type=FieldType.PHONE,
                        value=phone.group(0),
                        location=segment.location,
                        evidence=segment.text,
                        confidence=0.94,
                        label=definition.label if definition else "手机号",
                        existing_value=existing.get("contact.phone"),
                    )
                )
            name = _NAME_RE.search(segment.text)
            if name:
                definition = get_standard_field("person.full_name")
                result.append(
                    self._candidate(
                        task_id=task_id,
                        document_id=document.document_id,
                        field_id="person.full_name",
                        field_type=FieldType.TEXT,
                        value=name.group(1),
                        location=segment.location,
                        evidence=segment.text,
                        confidence=0.9,
                        label=definition.label if definition else "姓名",
                        existing_value=existing.get("person.full_name"),
                    )
                )
            date = _DATE_RE.search(segment.text)
            if date:
                field_id = {
                    "出生日期": "person.birth_date",
                    "入学时间": "education.start_date",
                    "毕业时间": "education.graduation_date",
                    "开始时间": "experience.start_date",
                    "结束时间": "experience.end_date",
                }[date.group("label")]
                definition = get_standard_field(field_id)
                normalized = (
                    re.sub(r"年|月", "-", date.group("value"))
                    .replace("日", "")
                    .replace("/", "-")
                    .replace(".", "-")
                )
                result.append(
                    self._candidate(
                        task_id=task_id,
                        document_id=document.document_id,
                        field_id=field_id,
                        field_type=FieldType.DATE,
                        value=normalized,
                        location=segment.location,
                        evidence=segment.text,
                        confidence=0.9,
                        label=definition.label if definition else date.group("label"),
                        existing_value=existing.get(field_id),
                    )
                )
            identifier = _ID_RE.search(segment.text)
            if identifier:
                definition = get_standard_field("person.id_number")
                result.append(
                    self._candidate(
                        task_id=task_id,
                        document_id=document.document_id,
                        field_id="person.id_number",
                        field_type=FieldType.TEXT,
                        value=identifier.group(0),
                        location=segment.location,
                        evidence=segment.text,
                        confidence=0.97,
                        label=definition.label if definition else "身份证/证件号码",
                        sensitivity=Sensitivity.HIGHLY_SENSITIVE,
                        existing_value=existing.get("person.id_number"),
                    )
                )
        return tuple(result)

    def preview(self, document: ParsedDocument, *, task_id: str | None = None) -> ImportTask:
        identifier = task_id or f"import-{uuid.uuid4().hex}"
        current = self._profiles.read()
        existing = {
            field.id: field.value for field in current.fields if field.scope is Scope.GLOBAL
        }
        task = ImportTask(
            task_id=identifier,
            document=document,
            candidates=self._candidates(identifier, document, existing),
            created_at=datetime.now(UTC),
            profile_version=current.profile_version,
        )
        self._tasks[identifier] = task
        return task

    def confirm(
        self,
        task_id: str,
        *,
        decisions: list[Mapping[str, Any]],
        profile_id: str,
        expected_profile_version: int,
    ) -> dict[str, Any]:
        task = self._task(task_id)
        if not profile_id or expected_profile_version < 0:
            raise ValueError("profile confirmation metadata is invalid")
        if expected_profile_version != task.profile_version:
            raise ValueError("profile version does not match import preview")
        if not decisions:
            raise ValueError("at least one import decision is required")
        by_id = {candidate["candidate_id"]: candidate for candidate in task.candidates}
        fields: list[dict[str, Any]] = []
        rejected: list[str] = []
        seen: set[str] = set()
        for decision in decisions:
            if not isinstance(decision, Mapping):
                raise TypeError("import decision is invalid")
            candidate_id = decision.get("candidate_id")
            if not isinstance(candidate_id, str) or candidate_id in seen:
                raise ValueError("import candidate id is invalid")
            seen.add(candidate_id)
            candidate = by_id.get(candidate_id)
            if candidate is None:
                raise ValueError("import candidate is unavailable")
            choice = decision.get("decision")
            if (
                choice not in {"accept", "modify", "reject"}
                or decision.get("user_confirmed") is not True
            ):
                raise ValueError("import decision is invalid")
            if choice == "reject":
                if "value" in decision:
                    raise ValueError("rejected candidate cannot include a value")
                rejected.append(str(candidate_id))
                continue
            if choice == "modify" and "value" not in decision:
                raise ValueError("modified candidate requires a value")
            value = decision.get("value", candidate["value"])
            target_scope = decision.get("target_scope", Scope.GLOBAL.value)
            if target_scope not in {scope.value for scope in Scope}:
                raise ValueError("target scope is invalid")
            fields.append(
                {
                    "id": candidate["field_id"],
                    "value": value,
                    "scope": target_scope,
                    "sensitivity": candidate.get("sensitivity", Sensitivity.NORMAL.value),
                    "requires_confirmation": True,
                    "confirmed": True,
                    "source": {
                        "kind": SourceKind.IMPORT.value,
                        "document_ref": task.document.document_id,
                        "location": candidate["source"].get("location"),
                    },
                }
            )
        snapshot = (
            self._profiles.upsert(
                profile_id,
                expected_profile_version=expected_profile_version,
                fields=fields,
                user_confirmed=True,
            )
            if fields
            else self._profiles.read(profile_id)
        )
        self._tasks.pop(task_id, None)
        return {
            "written_field_ids": [field["id"] for field in fields],
            "rejected_candidate_ids": rejected,
            "warnings": [],
            "profile_version": snapshot.profile_version,
        }

    def cancel(self, task_id: str) -> None:
        self._tasks.pop(task_id, None)
