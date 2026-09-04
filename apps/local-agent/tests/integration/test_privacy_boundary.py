"""T041 red privacy-boundary tests for every F001 lifecycle operation."""

from __future__ import annotations

import logging
from pathlib import Path

from resume_agent.profile.models import (
    FieldType,
    FieldValue,
    Scope,
    Sensitivity,
    Source,
    SourceKind,
)
from resume_agent.profile.service import ProfileService

PROFILE_ID = "profile-synthetic-f001-001"
SENSITIVE_VALUE = "SYNTHETIC-ID-NOT-VALID"


def _sensitive_field() -> FieldValue:
    from datetime import UTC, datetime

    return FieldValue(
        id="person.id_number",
        label="证件号",
        field_type=FieldType.TEXT,
        value=SENSITIVE_VALUE,
        scope=Scope.GLOBAL,
        sensitivity=Sensitivity.HIGHLY_SENSITIVE,
        requires_confirmation=True,
        confirmed=True,
        source=Source(kind=SourceKind.MANUAL),
        updated_at=datetime(2099, 1, 1, tzinfo=UTC),
    )


def test_profile_lifecycle_does_not_emit_sensitive_values_or_make_network_requests(
    tmp_path: Path, fake_profile_store: object, caplog: object, monkeypatch: object
) -> None:
    service = ProfileService(fake_profile_store, profile_id=PROFILE_ID)
    with caplog.at_level(logging.INFO):  # type: ignore[attr-defined]
        saved = service.upsert(
            PROFILE_ID, expected_profile_version=0, fields=[_sensitive_field()], user_confirmed=True
        )
        service.read(PROFILE_ID)
    assert SENSITIVE_VALUE not in " ".join(record.getMessage() for record in caplog.records)  # type: ignore[attr-defined]
    assert all("http" not in record.getMessage().lower() for record in caplog.records)  # type: ignore[attr-defined]
    assert not list(tmp_path.glob("*.upload"))
    assert saved.fields[0].value == SENSITIVE_VALUE
