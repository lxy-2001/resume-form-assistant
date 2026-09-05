from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class NormalizationIssue:
    code: str
    message: str
    severity: str = "warning"
    action: str | None = None


@dataclass(frozen=True, slots=True)
class NormalizedCandidate:
    candidate_id: str
    field_id: str
    label: str
    field_type: str
    original_value: Any
    normalized_value: Any
    source: dict[str, Any]
    confidence: float
    status: str
    requires_confirmation: bool = True
    issues: tuple[NormalizationIssue, ...] = ()
    existing_value: Any | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "candidate_id": self.candidate_id,
            "target_kind": "field",
            "field_id": self.field_id,
            "label": self.label,
            "field_type": self.field_type,
            "original_value": self.original_value,
            "normalized_value": self.normalized_value,
            "value": self.normalized_value,
            "source": self.source,
            "confidence": self.confidence,
            "status": self.status,
            "requires_confirmation": True,
            "issues": [
                {
                    "code": issue.code,
                    "message": issue.message,
                    "severity": issue.severity,
                    **({"action": issue.action} if issue.action else {}),
                }
                for issue in self.issues
            ],
        }
        if self.existing_value is not None:
            result["existing_value"] = self.existing_value
        return result


@dataclass(frozen=True, slots=True)
class RecordCandidate:
    candidate_id: str
    record_type: str
    fields: tuple[dict[str, Any], ...]
    source: dict[str, Any]
    confidence: float
    status: str = "new"
    requires_confirmation: bool = True
    issues: tuple[NormalizationIssue, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "target_kind": "record",
            "record_type": self.record_type,
            "fields": list(self.fields),
            "source": self.source,
            "confidence": self.confidence,
            "status": self.status,
            "requires_confirmation": True,
            "issues": [
                {"code": issue.code, "message": issue.message, "severity": issue.severity}
                for issue in self.issues
            ],
        }


@dataclass(slots=True)
class NormalizationTask:
    task_id: str
    source_task_id: str
    profile_id: str
    profile_version: int
    candidates: tuple[NormalizedCandidate, ...]
    records: tuple[RecordCandidate, ...] = ()
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    state: str = "awaiting_user_review"
    model_used: bool = False
    remote_data_sent: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "source_task_id": self.source_task_id,
            "profile_id": self.profile_id,
            "profile_version": self.profile_version,
            "task_state": self.state,
            "candidates": [candidate.to_dict() for candidate in self.candidates]
            + [candidate.to_dict() for candidate in self.records],
            "issues": [],
            "model_used": self.model_used,
            "remote_data_sent": self.remote_data_sent,
            "consent_recorded": False,
        }
