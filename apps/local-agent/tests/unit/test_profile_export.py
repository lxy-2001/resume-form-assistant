"""T036 red tests for local-only, selected-scope profile export."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from resume_agent.profile import export_service as export_module
from resume_agent.profile.errors import (
    ConfirmationRequiredError,
    ExportFailedError,
    InvalidProfileSelectionError,
    StaleProfileVersionError,
)
from resume_agent.profile.models import (
    FieldType,
    FieldValue,
    ProfileSnapshot,
    RepeatableRecord,
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


def test_export_field_value_selector_keeps_only_the_requested_scope(
    tmp_path: Path,
) -> None:
    timestamp = datetime(2099, 1, 1, tzinfo=UTC)
    snapshot = ProfileSnapshot(
        profile_id=PROFILE_ID,
        profile_version=1,
        is_empty=False,
        fields=[
            _field("custom.city", "北京", scope=Scope.GLOBAL),
            _field(
                "custom.city",
                "上海",
                scope=Scope.WEBSITE,
                context="jobs.example.invalid",
            ),
        ],
        records=[],
        field_definitions=[],
        created_at=timestamp,
        updated_at=timestamp,
    )

    destination = tmp_path / "scoped.json"
    result = export_module.export_profile_snapshot(
        snapshot,
        selection={
            "field_values": [
                {
                    "id": "custom.city",
                    "scope": "website",
                    "scope_context": "jobs.example.invalid",
                }
            ]
        },
        destination=destination,
    )

    payload = destination.read_text(encoding="utf-8")
    assert "上海" in payload
    assert "北京" not in payload
    assert result["exported_field_ids"] == ["custom.city"]
    assert result["exported_scopes"] == ["website"]


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


@pytest.mark.parametrize(
    ("selection", "reason"),
    [
        ({"field_ids": ["person.missing"]}, "unknown field"),
        ({"record_ids": ["education-missing-001"]}, "unknown record"),
    ],
)
def test_export_rejects_unknown_ids_without_creating_a_file(
    tmp_path: Path,
    fake_profile_store: object,
    selection: dict[str, list[str]],
    reason: str,
) -> None:
    del reason
    service = ProfileService(fake_profile_store, profile_id=PROFILE_ID)
    service.upsert(
        PROFILE_ID,
        expected_profile_version=0,
        fields=[_field("person.full_name", "Synthetic Person")],
        user_confirmed=True,
    )
    destination = tmp_path / "unknown-selection.json"

    with pytest.raises(InvalidProfileSelectionError):
        service.export(
            PROFILE_ID,
            expected_profile_version=1,
            selection=selection,
            destination=destination,
            user_confirmed=True,
        )

    assert not destination.exists()


def test_export_reports_only_scopes_present_in_selected_output(tmp_path: Path) -> None:
    timestamp = datetime(2099, 1, 1, tzinfo=UTC)
    record = RepeatableRecord(
        record_id="education-synthetic-001",
        record_type="education",
        position=0,
        fields=[
            _field("education.school_name", "Synthetic University", scope=Scope.GLOBAL),
            _field(
                "education.major",
                "Synthetic Major",
                scope=Scope.WEBSITE,
                context="jobs.example.invalid",
            ),
        ],
        confirmed=True,
        created_at=timestamp,
        updated_at=timestamp,
    )
    snapshot = ProfileSnapshot(
        profile_id=PROFILE_ID,
        profile_version=1,
        is_empty=False,
        fields=[],
        records=[record],
        field_definitions=[],
        created_at=timestamp,
        updated_at=timestamp,
    )

    result = export_module.export_profile_snapshot(
        snapshot,
        selection={"scopes": ["global"]},
        destination=tmp_path / "scopes.json",
    )

    assert result["exported_scopes"] == ["global"]


def test_export_no_clobber_install_preserves_file_created_during_preflight(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = tmp_path / "race.json"

    def race_link(_: Path, target: Path) -> None:
        target.write_bytes(b"created-by-racer")
        raise FileExistsError("destination appeared")

    monkeypatch.setattr(export_module.os, "link", race_link)

    with pytest.raises(ExportFailedError):
        export_module._write_atomic(
            destination,
            b"replacement",
            overwrite_existing=False,
        )

    assert destination.read_bytes() == b"created-by-racer"
