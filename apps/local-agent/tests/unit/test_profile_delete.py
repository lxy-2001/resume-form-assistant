"""T037 red tests for confirmed, idempotent profile deletion."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from resume_agent.profile.errors import (
    ConfirmationRequiredError,
    InvalidProfileSelectionError,
    StaleProfileVersionError,
)
from resume_agent.profile.models import (
    FieldType,
    FieldValue,
    ProfileRecordType,
    RepeatableRecord,
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


def _record(record_id: str) -> RepeatableRecord:
    return RepeatableRecord(
        record_id=record_id,
        record_type=ProfileRecordType.EDUCATION,
        position=0,
        fields=[_field("education.school_name", "Synthetic University")],
        confirmed=True,
        created_at=datetime(2099, 1, 1, tzinfo=UTC),
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


def test_delete_field_drops_empty_record_and_reports_record_id(fake_profile_store: object) -> None:
    service = ProfileService(fake_profile_store, profile_id=PROFILE_ID)
    saved = service.upsert_record(
        PROFILE_ID,
        expected_profile_version=0,
        record=_record("education-synthetic-001"),
        user_confirmed=True,
    )

    result = service.delete(
        PROFILE_ID,
        expected_profile_version=saved.profile_version,
        selection={"field_ids": ["education.school_name"]},
        user_confirmed=True,
    )

    assert result["deleted_field_ids"] == ["education.school_name"]
    assert result["deleted_record_ids"] == ["education-synthetic-001"]
    assert service.read(PROFILE_ID).records == []


def test_delete_field_value_selector_removes_only_the_requested_scope(
    fake_profile_store: object,
) -> None:
    from resume_agent.profile.models import CustomFieldDefinition

    service = ProfileService(fake_profile_store, profile_id=PROFILE_ID)
    timestamp = datetime(2099, 1, 1, tzinfo=UTC)
    definition = CustomFieldDefinition(
        id="custom.delete-scope",
        label="目标城市",
        field_type=FieldType.TEXT,
        default_sensitivity=Sensitivity.NORMAL,
        requires_confirmation=True,
        is_custom=True,
        allowed_scopes=[Scope.GLOBAL, Scope.WEBSITE],
        created_at=timestamp,
        updated_at=timestamp,
    )
    created = service.create_custom_field(
        PROFILE_ID,
        expected_profile_version=0,
        definition=definition,
        value="北京",
        scope=Scope.GLOBAL,
        user_confirmed=True,
    )
    saved = service.update_custom_field(
        PROFILE_ID,
        expected_profile_version=created.profile_version,
        field_id=definition.id,
        value="上海",
        scope=Scope.WEBSITE,
        scope_context="jobs.example.invalid",
        user_confirmed=True,
    )

    result = service.delete(
        PROFILE_ID,
        expected_profile_version=saved.profile_version,
        selection={
            "field_values": [
                {
                    "id": definition.id,
                    "scope": "website",
                    "scope_context": "jobs.example.invalid",
                }
            ]
        },
        user_confirmed=True,
    )

    assert result["deleted_field_ids"] == [definition.id]
    remaining = service.read(PROFILE_ID).fields
    assert [(field.scope, field.scope_context, field.value) for field in remaining] == [
        (Scope.GLOBAL, None, "北京")
    ]


def test_delete_custom_field_removes_record_values_without_dangling_empty_record(
    fake_profile_store: object,
) -> None:
    from resume_agent.profile.models import CustomFieldDefinition, PageOption

    service = ProfileService(fake_profile_store, profile_id=PROFILE_ID)
    definition = CustomFieldDefinition(
        id="custom.record-only",
        label="记录自定义字段",
        field_type=FieldType.TEXT,
        default_sensitivity=Sensitivity.NORMAL,
        requires_confirmation=False,
        is_custom=True,
        allowed_scopes=[Scope.GLOBAL],
        created_at=datetime(2099, 1, 1, tzinfo=UTC),
        updated_at=datetime(2099, 1, 1, tzinfo=UTC),
    )
    # Keep the import explicit in the test to ensure the model's options path
    # remains covered without changing the production contract.
    del PageOption
    created = service.create_custom_field(
        PROFILE_ID,
        expected_profile_version=0,
        definition=definition,
        value="Synthetic custom value",
        scope=Scope.GLOBAL,
        user_confirmed=True,
    )
    record = _record("education-custom-only").model_copy(
        update={"fields": [next(field for field in created.fields if field.id == definition.id)]}
    )
    saved = service.upsert_record(
        PROFILE_ID,
        expected_profile_version=created.profile_version,
        record=record,
        user_confirmed=True,
    )

    deleted = service.delete_custom_field(
        PROFILE_ID,
        expected_profile_version=saved.profile_version,
        field_id=definition.id,
        user_confirmed=True,
    )

    assert deleted.records == []
    assert all(field.id != definition.id for field in deleted.fields)


def test_delete_rejects_unknown_selected_ids_without_mutating(fake_profile_store: object) -> None:
    service = ProfileService(fake_profile_store, profile_id=PROFILE_ID)
    saved = service.upsert(
        PROFILE_ID,
        expected_profile_version=0,
        fields=[_field("person.full_name", "Synthetic Person")],
        user_confirmed=True,
    )
    writes_before = fake_profile_store.write_calls

    with pytest.raises(InvalidProfileSelectionError):
        service.delete(
            PROFILE_ID,
            expected_profile_version=saved.profile_version,
            selection={"record_ids": ["education-missing-001"]},
            user_confirmed=True,
        )

    assert fake_profile_store.write_calls == writes_before
    assert service.read(PROFILE_ID).fields[0].value == "Synthetic Person"


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
