"""T036 red tests for local-only, selected-scope profile export."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from resume_agent.profile.errors import (
    ConfirmationRequiredError,
    ExportFailedError,
    InvalidProfileSelectionError,
    StaleProfileVersionError,
)
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


def _field(
    field_id: str, value: str, *, scope: Scope = Scope.GLOBAL, context: str | None = None
) -> FieldValue:
    return FieldValue(
        id=field_id,
        label=field_id,
        field_type=FieldType.EMAIL if field_id == "contact.email" else FieldType.TEXT,
        value=value,
        scope=scope,
        scope_context=context,
        sensitivity=Sensitivity.NORMAL,
        requires_confirmation=False,
        confirmed=True,
        source=Source(kind=SourceKind.MANUAL),
        updated_at=datetime(2099, 1, 1, tzinfo=UTC),
    )


def test_export_writes_only_selected_fields_and_never_uploads(
    tmp_path: Path, fake_profile_store: object
) -> None:
    service = ProfileService(fake_profile_store, profile_id=PROFILE_ID)
    service.upsert(
        PROFILE_ID,
        expected_profile_version=0,
        fields=[
            _field("person.full_name", "Synthetic Person"),
            _field("contact.email", "person@example.invalid"),
        ],
        user_confirmed=True,
    )

    destination = tmp_path / "selected-profile.json"
    result = service.export(
        PROFILE_ID,
        expected_profile_version=1,
        selection={"field_ids": ["person.full_name"]},
        destination=destination,
        user_confirmed=True,
    )

    assert result["status"] == "written"
    assert result["exported_field_ids"] == ["person.full_name"]
    assert destination.exists()
    assert "contact.email" not in destination.read_text(encoding="utf-8")
    assert "upload_url" not in result


def test_export_requires_confirmation_and_rejects_stale_version(
    tmp_path: Path, fake_profile_store: object
) -> None:
    service = ProfileService(fake_profile_store, profile_id=PROFILE_ID)
    saved = service.upsert(
        PROFILE_ID,
        expected_profile_version=0,
        fields=[_field("person.full_name", "Synthetic Person")],
        user_confirmed=True,
    )

    with pytest.raises(ConfirmationRequiredError):
        service.export(
            PROFILE_ID,
            expected_profile_version=saved.profile_version,
            selection={"all_profile_data": True},
            destination=tmp_path / "x.json",
            user_confirmed=False,
        )
    with pytest.raises(StaleProfileVersionError):
        service.export(
            PROFILE_ID,
            expected_profile_version=0,
            selection={"all_profile_data": True},
            destination=tmp_path / "x.json",
            user_confirmed=True,
        )


def test_export_rejects_remote_destination_and_does_not_leave_partial_file(
    tmp_path: Path, fake_profile_store: object
) -> None:
    service = ProfileService(fake_profile_store, profile_id=PROFILE_ID)
    service.upsert(
        PROFILE_ID,
        expected_profile_version=0,
        fields=[_field("person.full_name", "Synthetic Person")],
        user_confirmed=True,
    )

    with pytest.raises((ExportFailedError, ValueError)):
        service.export(
            PROFILE_ID,
            expected_profile_version=1,
            selection={"all_profile_data": True},
            destination="https://example.invalid/profile.json",
            user_confirmed=True,
        )
    assert not (tmp_path / "profile.json").exists()


def test_export_rejects_nested_selection_values_as_a_client_error(
    tmp_path: Path, fake_profile_store: object
) -> None:
    service = ProfileService(fake_profile_store, profile_id=PROFILE_ID)
    service.upsert(
        PROFILE_ID,
        expected_profile_version=0,
        fields=[_field("person.full_name", "Synthetic Person")],
        user_confirmed=True,
    )

    with pytest.raises(InvalidProfileSelectionError):
        service.export(
            PROFILE_ID,
            expected_profile_version=1,
            selection={"field_ids": [["person.full_name"]]},
            destination=tmp_path / "invalid.json",
            user_confirmed=True,
        )
