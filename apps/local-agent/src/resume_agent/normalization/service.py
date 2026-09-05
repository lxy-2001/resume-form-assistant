from __future__ import annotations

import uuid
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

from resume_agent.imports.service import ImportService
from resume_agent.normalization.models import (
    NormalizationTask,
    NormalizedCandidate,
)
from resume_agent.normalization.records import group_record_candidates
from resume_agent.normalization.rules import normalize_value
from resume_agent.profile.models import Scope, SourceKind
from resume_agent.profile.service import ProfileService
from resume_agent.profile.standard_fields import get_standard_field


def _field_type_for(field_id: str) -> str:
    definition = get_standard_field(field_id)
    return definition.field_type.value if definition is not None else "text"


class NormalizationService:
    """Create review-only normalization tasks and persist explicit decisions."""

    def __init__(
        self,
        profile_service: ProfileService,
        import_service: ImportService,
        *,
        task_ttl: timedelta = timedelta(minutes=15),
    ) -> None:
        self._profiles = profile_service
        self._imports = import_service
        self._tasks: dict[str, NormalizationTask] = {}
        self._task_ttl = task_ttl

    def _task(self, task_id: str) -> NormalizationTask:
        task = self._tasks.get(task_id)
        if task is None:
            raise ValueError("normalization task is unavailable")
        if datetime.now(UTC) - task.created_at > self._task_ttl:
            task.state = "expired"
            self._tasks.pop(task_id, None)
            raise ValueError("normalization task has expired")
        if task.state in {"cancelled", "completed", "expired"}:
            raise ValueError("normalization task is no longer writable")
        return task

    def preview(
        self,
        source_task_id: str,
        *,
        profile_id: str,
        task_id: str | None = None,
    ) -> NormalizationTask:
        source = self._imports.get_task(source_task_id)
        current = self._profiles.read(profile_id)
        existing = {(field.id, field.scope): field.value for field in current.fields}
        identifier = task_id or f"normalize-{uuid.uuid4().hex}"
        candidates: list[NormalizedCandidate] = []
        for raw in source.candidates:
            field_id = str(raw["field_id"])
            normalized, confidence, issues = normalize_value(raw["field_type"], raw.get("value"))
            current_value = existing.get((field_id, Scope.GLOBAL))
            status = "new"
            if issues:
                status = "invalid"
            elif current_value == normalized:
                status = "unchanged"
            elif current_value is not None:
                status = "conflict"
            candidate = NormalizedCandidate(
                candidate_id=f"{identifier}-{len(candidates) + 1}",
                field_id=field_id,
                label=str(raw.get("label") or field_id),
                field_type=str(raw["field_type"]),
                original_value=raw.get("value"),
                normalized_value=normalized,
                source={**dict(raw.get("source") or {}), "detail": "F002 candidate"},
                confidence=min(float(raw.get("confidence", confidence)), confidence or 0.0),
                status=status,
                issues=tuple(issues),
                existing_value=current_value,
            )
            candidates.append(candidate)
        records = group_record_candidates(tuple(candidates), identifier)
        task = NormalizationTask(
            task_id=identifier,
            source_task_id=source_task_id,
            profile_id=current.profile_id,
            profile_version=current.profile_version,
            candidates=tuple(candidates),
            records=tuple(records),
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
        if profile_id != task.profile_id or expected_profile_version != task.profile_version:
            raise ValueError("profile version does not match normalization preview")
        by_id = {candidate.candidate_id: candidate for candidate in task.candidates}
        record_by_id = {candidate.candidate_id: candidate for candidate in task.records}
        fields: list[dict[str, Any]] = []
        records: list[dict[str, Any]] = []
        rejected: list[str] = []
        seen: set[str] = set()
        for decision in decisions:
            candidate_id = decision.get("candidate_id")
            if not isinstance(candidate_id, str) or candidate_id in seen:
                raise ValueError("normalization candidate id is invalid")
            seen.add(candidate_id)
            candidate = by_id.get(candidate_id)
            record_candidate = record_by_id.get(candidate_id)
            if candidate is None and record_candidate is None:
                raise ValueError("normalization candidate is unavailable")
            choice = decision.get("decision")
            if (
                choice not in {"accept", "modify", "skip", "reject"}
                or decision.get("user_confirmed") is not True
            ):
                raise ValueError("normalization decision is invalid")
            if choice in {"skip", "reject"}:
                rejected.append(candidate_id)
                continue
            if record_candidate is not None:
                if choice == "modify":
                    raise ValueError("record modification requires field-level decisions")
                if choice == "accept":
                    now = datetime.now(UTC)
                    records.append(
                        {
                            "record_id": f"normalized-{candidate_id}",
                            "record_type": record_candidate.record_type,
                            "position": len(records),
                            "fields": [
                                {
                                    **item,
                                    "label": item["id"],
                                    "field_type": _field_type_for(item["id"]),
                                    "scope": Scope.GLOBAL.value,
                                    "sensitivity": "normal",
                                    "requires_confirmation": True,
                                    "confirmed": True,
                                    "updated_at": now.isoformat(),
                                }
                                for item in record_candidate.fields
                            ],
                            "confirmed": True,
                            "created_at": now.isoformat(),
                            "updated_at": now.isoformat(),
                        }
                    )
                continue
            assert candidate is not None
            value = decision.get("value", candidate.normalized_value)
            if choice == "modify":
                value, _, issues = normalize_value(candidate.field_type, value)
                if issues:
                    raise ValueError("modified value is invalid")
            fields.append(
                {
                    "id": candidate.field_id,
                    "label": candidate.label,
                    "field_type": candidate.field_type,
                    "value": value,
                    "scope": decision.get("target_scope", Scope.GLOBAL.value),
                    "sensitivity": "normal",
                    "requires_confirmation": True,
                    "confirmed": True,
                    "source": {
                        "kind": SourceKind.USER_CORRECTION.value
                        if choice == "modify"
                        else SourceKind.IMPORT.value,
                        "document_ref": candidate.source.get("document_ref"),
                        "location": candidate.source.get("location"),
                    },
                }
            )
        if not fields and not records:
            self._tasks.pop(task_id, None)
            return {
                "written_field_ids": [],
                "rejected_candidate_ids": rejected,
                "profile_version": task.profile_version,
                "warnings": [],
            }
        snapshot = self._profiles.upsert_extended(
            profile_id,
            expected_profile_version=expected_profile_version,
            fields=fields,
            records=records,
            user_confirmed=True,
        )
        self._tasks.pop(task_id, None)
        return {
            "written_field_ids": [field["id"] for field in fields],
            "written_record_ids": [record["record_id"] for record in records],
            "rejected_candidate_ids": rejected,
            "profile_version": snapshot.profile_version,
            "warnings": [],
        }

    def cancel(self, task_id: str) -> None:
        task = self._tasks.get(task_id)
        if task is not None:
            task.state = "cancelled"
            self._tasks.pop(task_id, None)


__all__ = ["NormalizationService"]
