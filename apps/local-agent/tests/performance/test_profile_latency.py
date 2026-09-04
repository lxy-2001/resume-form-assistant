"""T047 performance coverage for the largest F001 in-memory profile shape."""

from __future__ import annotations

from datetime import UTC, datetime
from time import perf_counter

from resume_agent.profile.models import (
    FieldType,
    FieldValue,
    ProfileRecordType,
    ProfileSnapshot,
    RepeatableRecord,
    Scope,
    Sensitivity,
    Source,
    SourceKind,
)
from resume_agent.profile.service import ProfileService

PROFILE_ID = "profile-synthetic-f001-performance"
TIMESTAMP = datetime(2099, 1, 1, tzinfo=UTC)


def _field(field_id: str, value: str) -> FieldValue:
    return FieldValue(
        id=field_id,
        label=field_id,
        field_type=FieldType.TEXT,
        value=value,
        scope=Scope.GLOBAL,
        sensitivity=Sensitivity.NORMAL,
        requires_confirmation=False,
        confirmed=True,
        source=Source(kind=SourceKind.MANUAL),
        updated_at=TIMESTAMP,
    )


def _large_snapshot() -> ProfileSnapshot:
    fields = [_field(f"synthetic.field.{index:03d}", f"value-{index}") for index in range(500)]
    records = [
        RepeatableRecord(
            record_id=f"synthetic.record.{index:03d}",
            record_type=ProfileRecordType.PROJECT,
            position=index,
            fields=[_field(f"synthetic.record-field.{index:03d}", f"record-{index}")],
            confirmed=True,
            created_at=TIMESTAMP,
            updated_at=TIMESTAMP,
        )
        for index in range(100)
    ]
    return ProfileSnapshot(
        profile_id=PROFILE_ID,
        profile_version=1,
        is_empty=False,
        fields=fields,
        records=records,
        field_definitions=[],
        created_at=TIMESTAMP,
        updated_at=TIMESTAMP,
    )


def test_large_snapshot_read_p95_under_one_second(fake_profile_store: object) -> None:
    """Reading 500 fields and 100 records stays responsive on the local service seam."""

    snapshot = _large_snapshot()
    fake_profile_store.snapshot = snapshot  # type: ignore[attr-defined]
    service = ProfileService(fake_profile_store, profile_id=PROFILE_ID)

    elapsed: list[float] = []
    for _ in range(7):
        started = perf_counter()
        result = service.read(PROFILE_ID)
        elapsed.append(perf_counter() - started)

    assert len(result.fields) == 500
    assert len(result.records) == 100
    p95 = sorted(elapsed)[int(len(elapsed) * 0.95) - 1]
    assert p95 < 1.0, f"large snapshot read p95 was {p95:.3f}s"
