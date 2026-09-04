from __future__ import annotations

from datetime import UTC, datetime

import pytest
from test_repeatable_records import PROFILE_ID, _record

from resume_agent.profile.errors import CustomFieldConflictError, InvalidFieldValueError
from resume_agent.profile.models import (
    CustomFieldDefinition,
    FieldType,
    ProfileRecordType,
    Scope,
    Sensitivity,
)
from resume_agent.profile.service import ProfileService
from resume_agent.storage.base import ProfileStore


def test_extended_rejects_unknown_delete_ids_atomically(fake_profile_store: ProfileStore) -> None:
    service = ProfileService(fake_profile_store, profile_id=PROFILE_ID)
    with pytest.raises(InvalidFieldValueError):
        service.upsert_extended(
            PROFILE_ID,
            expected_profile_version=0,
            delete_record_ids=["missing-record"],
            user_confirmed=True,
        )
    assert fake_profile_store.write_calls == 0


def test_extended_rejects_deleting_standard_definition(fake_profile_store: ProfileStore) -> None:
    service = ProfileService(fake_profile_store, profile_id=PROFILE_ID)
    with pytest.raises(CustomFieldConflictError):
        service.upsert_extended(
            PROFILE_ID,
            expected_profile_version=0,
            delete_custom_field_definition_ids=["person.full_name"],
            user_confirmed=True,
        )
    assert fake_profile_store.write_calls == 0


def test_extended_rejects_duplicate_record_ids_atomically(fake_profile_store: ProfileStore) -> None:
    service = ProfileService(fake_profile_store, profile_id=PROFILE_ID)
    record = _record(
        "education-duplicate", ProfileRecordType.EDUCATION, 0, school_or_project="Synthetic"
    )
    with pytest.raises(InvalidFieldValueError):
        service.upsert_extended(
            PROFILE_ID,
            expected_profile_version=0,
            records=[record, record.model_copy(deep=True)],
            user_confirmed=True,
        )
    assert fake_profile_store.write_calls == 0


def test_standard_upsert_preserves_existing_custom_definition(
    fake_profile_store: ProfileStore,
) -> None:
    service = ProfileService(fake_profile_store, profile_id=PROFILE_ID)
    stamp = datetime(2099, 1, 1, tzinfo=UTC)
    definition = CustomFieldDefinition(
        id="custom.keep_me",
        label="保留字段",
        field_type=FieldType.TEXT,
        default_sensitivity=Sensitivity.NORMAL,
        requires_confirmation=False,
        is_custom=True,
        allowed_scopes=[Scope.GLOBAL],
        created_at=stamp,
        updated_at=stamp,
    )
    created = service.create_custom_field(
        PROFILE_ID,
        expected_profile_version=0,
        definition=definition,
        value="Synthetic",
        scope=Scope.GLOBAL,
        user_confirmed=True,
    )
    updated = service.upsert(
        PROFILE_ID,
        expected_profile_version=created.profile_version,
        fields=[
            {
                "id": "person.full_name",
                "value": "Synthetic User",
                "scope": "global",
                "confirmed": True,
                "source": {"kind": "manual"},
            }
        ],
        user_confirmed=True,
    )
    assert any(item.id == definition.id and item.is_custom for item in updated.field_definitions)


def test_extended_deletes_top_level_value_but_keeps_definition(
    fake_profile_store: ProfileStore,
) -> None:
    service = ProfileService(fake_profile_store, profile_id=PROFILE_ID)
    created = service.upsert_extended(
        PROFILE_ID,
        expected_profile_version=0,
        fields=[
            {
                "id": "person.full_name",
                "value": "Synthetic",
                "scope": "global",
                "confirmed": True,
                "source": {"kind": "manual"},
            }
        ],
        user_confirmed=True,
    )
    deleted = service.upsert_extended(
        PROFILE_ID,
        expected_profile_version=created.profile_version,
        delete_field_ids=["person.full_name"],
        user_confirmed=True,
    )
    assert deleted.fields == []
    assert any(item.id == "person.full_name" for item in deleted.field_definitions)
