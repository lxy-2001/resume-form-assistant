from __future__ import annotations

from collections import defaultdict

from resume_agent.normalization.models import NormalizedCandidate, RecordCandidate


def group_record_candidates(
    candidates: tuple[NormalizedCandidate, ...], task_id: str
) -> tuple[RecordCandidate, ...]:
    """Group clear education/experience fields by their source location."""

    by_location: defaultdict[str, list[NormalizedCandidate]] = defaultdict(list)
    for candidate in candidates:
        if candidate.field_id.startswith(("education.", "experience.")):
            by_location[str(candidate.source.get("location") or "unknown")].append(candidate)
    records: list[RecordCandidate] = []
    for index, (location, grouped) in enumerate(by_location.items(), start=1):
        prefix = grouped[0].field_id.split(".", 1)[0]
        joined = " ".join(str(item.original_value) for item in grouped)
        record_type = "education" if prefix == "education" else "work"
        if "项目" in joined:
            record_type = "project"
        elif "实习" in joined:
            record_type = "internship"
        records.append(
            RecordCandidate(
                candidate_id=f"{task_id}-record-{index}",
                record_type=record_type,
                fields=tuple(
                    {
                        "id": item.field_id,
                        "value": item.normalized_value,
                        "source": item.source,
                        "sensitivity": item.sensitivity,
                    }
                    for item in grouped
                ),
                source={"kind": "import", "location": location},
                confidence=min(item.confidence for item in grouped),
                normalized_value="; ".join(str(item.normalized_value) for item in grouped),
                status="conflict" if any(item.status == "conflict" for item in grouped) else "new",
            )
        )
    return tuple(records)
