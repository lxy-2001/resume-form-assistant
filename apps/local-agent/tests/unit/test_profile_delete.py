"""T037 red tests for confirmed, idempotent profile deletion."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from resume_agent.profile.errors import ConfirmationRequiredError, StaleProfileVersionError
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


def _field(field_id: str, value: str) -> FieldValue:
    return FieldValue(
        id=field_id,
        label=field_id,
        field_type=FieldType.EMAIL if field_id == "contact.email" else FieldType.TEXT,
        value=value,
        scope=Scope.GLOBAL,
        sensitivity=Sensitivity.NORMAL,
        requires_confirmation=False,
        confirmed=True,
        source=Source(kind=SourceKind.MANUAL),
        updated_at=datetime(2099, 1, 1, tzinfo=UTC),
    )


def test_delete_selected_field_preserves_other_data_and_reports_ids(
    fake_profile_store: object,
) -> None:
    service = ProfileService(fake_profile_store, profile_id=PROFILE_ID)
    saved = service.upsert(
        PROFILE_ID,
        expected_profile_version=0,
        fields=[
            _field("person.full_name", "Synthetic Person"),
            _field("contact.email", "person@example.invalid"),
        ],
        user_confirmed=True,
    )

    result = service.delete(
        PROFILE_ID,
        expected_profile_version=saved.profile_version,
        selection={"field_ids": ["person.full_name"]},
        user_confirmed=True,
    )

    assert result["deleted_field_ids"] == ["person.full_name"]
    assert {field.id for field in service.read(PROFILE_ID).fields} == {"contact.email"}
    assert result["all_data_deleted"] is False


def test_delete_requires_confirmation_and_is_idempotent(fake_profile_store: object) -> None:
    service = ProfileService(fake_profile_store, profile_id=PROFILE_ID)
    saved = service.upsert(
        PROFILE_ID,
        expected_profile_version=0,
        fields=[_field("person.full_name", "Synthetic Person")],
        user_confirmed=True,
    )

    with pytest.raises(ConfirmationRequiredError):
        service.delete(
            PROFILE_ID,
            expected_profile_version=saved.profile_version,
            selection={"delete_all": True},
            user_confirmed=False,
        )
    first = service.delete(
        PROFILE_ID,
        expected_profile_version=saved.profile_version,
        selection={"delete_all": True},
        user_confirmed=True,
    )
    second = service.delete(
        PROFILE_ID,
        expected_profile_version=first["profile_version"],
        selection={"delete_all": True},
        user_confirmed=True,
    )

    assert first["all_data_deleted"] is True
    assert second["all_data_deleted"] is True
    assert service.read(PROFILE_ID).is_empty is True


def test_delete_rejects_stale_version_without_mutating(fake_profile_store: object) -> None:
    service = ProfileService(fake_profile_store, profile_id=PROFILE_ID)
    service.upsert(
        PROFILE_ID,
        expected_profile_version=0,
        fields=[_field("person.full_name", "Synthetic Person")],
        user_confirmed=True,
    )
    writes_before = fake_profile_store.write_calls
    with pytest.raises(StaleProfileVersionError):
        service.delete(
            PROFILE_ID,
            expected_profile_version=0,
            selection={"field_ids": ["person.full_name"]},
            user_confirmed=True,
        )
    assert fake_profile_store.write_calls == writes_before
