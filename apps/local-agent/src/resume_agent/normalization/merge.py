from __future__ import annotations

from collections.abc import Iterable

from resume_agent.normalization.models import RecordCandidate


def classify_record_status(candidate: RecordCandidate, existing_records: Iterable[object]) -> str:
    """Classify a record conservatively using type and normalized field values."""

    for existing in existing_records:
        existing_type = getattr(existing, "record_type", None)
        if getattr(existing_type, "value", existing_type) != candidate.record_type:
            continue
        existing_values = {
            getattr(field, "value", None) for field in getattr(existing, "fields", [])
        }
        candidate_values = {field.get("value") for field in candidate.fields}
        if candidate_values and candidate_values.issubset(existing_values):
            return "unchanged"
        if candidate_values & existing_values:
            return "possible_duplicate"
    return candidate.status


def record_match_details(
    candidate: RecordCandidate, existing_records: Iterable[object]
) -> tuple[str | None, dict[str, object] | None]:
    """Return a privacy-safe explanation and summary for the first matching record."""

    for existing in existing_records:
        existing_type = getattr(existing, "record_type", None)
        if getattr(existing_type, "value", existing_type) != candidate.record_type:
            continue
        existing_values = [
            getattr(field, "value", None) for field in getattr(existing, "fields", [])
        ]
        candidate_values = [field.get("value") for field in candidate.fields]
        overlap = [
            value for value in candidate_values if value in existing_values and value is not None
        ]
        if not overlap:
            continue
        reason = "已有记录包含相同字段值" if len(overlap) == 1 else "已有记录包含多个相同字段值"
        summary = {
            "record_id": getattr(existing, "record_id", None),
            "record_type": getattr(existing_type, "value", existing_type),
            "fields": [{"value": value} for value in existing_values if value is not None],
        }
        return reason, summary
    return None, None
