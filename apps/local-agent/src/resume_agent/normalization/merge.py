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
