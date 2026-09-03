"""T013 domain-level acceptance tests for the local profile service.

The service implementation is deliberately absent while this task is authored.  These tests fix
the observable snapshot/version/confirmation semantics before storage or HTTP concerns are added.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest

from resume_agent.profile.errors import (
    ConfirmationRequiredError,
    InvalidFieldValueError,
    StaleProfileVersionError,
)
from resume_agent.profile.models import (
    FieldType,
    FieldValue,
    ProfileSnapshot,
    Scope,
    Sensitivity,
    Source,
    SourceKind,
)
from resume_agent.profile.service import ProfileService
from resume_agent.storage.base import ProfileStore

PROFILE_ID = "profile-synthetic-f001-001"


def _field(
    field_id: str,
    value: object,
    timestamp: datetime,
    *,
    field_type: FieldType = FieldType.TEXT,
    sensitivity: Sensitivity = Sensitivity.NORMAL,
    requires_confirmation: bool = False,
) -> FieldValue:
    return FieldValue(
        id=field_id,
        label=field_id.replace(".", " "),
        field_type=field_type,
        value=value,
        scope=Scope.GLOBAL,
        sensitivity=sensitivity,
        requires_confirmation=requires_confirmation,
        confirmed=True,
        source=Source(kind=SourceKind.MANUAL),
        updated_at=timestamp,
    )


class _Clock:
    def __init__(self, values: Iterator[datetime]) -> None:
        self._values = values

    def __call__(self) -> datetime:
        return next(self._values)


def _service(store: ProfileStore, *times: datetime) -> ProfileService:
    return ProfileService(
        store,
        profile_id=PROFILE_ID,
        clock=_Clock(iter(times)) if times else None,
    )


def test_empty_read_returns_distinct_empty_snapshot_without_write(fake_profile_store: ProfileStore) -> None:
    service = _service(fake_profile_store)

    snapshot = service.read(PROFILE_ID)

    assert isinstance(snapshot, ProfileSnapshot)
    assert snapshot.profile_id == PROFILE_ID
    assert snapshot.profile_version == 0
    assert snapshot.is_empty is True
    assert snapshot.fields == []
    assert snapshot.records == []
    assert fake_profile_store.write_calls == 0


def test_create_persist_restart_and_read_back(
    fake_profile_store: ProfileStore,
) -> None:
    first = datetime(2099, 1, 1, tzinfo=UTC)
    second = datetime(2099, 1, 2, tzinfo=UTC)
    service = _service(fake_profile_store, first, second)
    fields = [_field("person.full_name", "Synthetic Test Person", first), _field("contact.email", "person@example.invalid", first, field_type=FieldType.EMAIL)]

    saved = service.upsert(
        PROFILE_ID,
        expected_profile_version=0,
        fields=fields,
        user_confirmed=True,
    )
    restarted = ProfileService(fake_profile_store, profile_id=PROFILE_ID)
    loaded = restarted.read(PROFILE_ID)

    assert saved.profile_version == 1
    assert loaded.to_dict() == saved.to_dict()
    assert loaded.updated_at == second
    assert {field.id for field in loaded.fields} == {"person.full_name", "contact.email"}


def test_edit_replaces_only_selected_field_and_preserves_creation_time(
    fake_profile_store: ProfileStore,
) -> None:
    created = datetime(2099, 2, 1, tzinfo=UTC)
    edited = datetime(2099, 2, 2, tzinfo=UTC)
    service = _service(fake_profile_store, created, edited)
    initial = service.upsert(
        PROFILE_ID,
        expected_profile_version=0,
        fields=[
            _field("person.full_name", "Before", created),
            _field("contact.email", "person@example.invalid", created, field_type=FieldType.EMAIL),
        ],
        user_confirmed=True,
    )

    updated = service.upsert(
        PROFILE_ID,
        expected_profile_version=initial.profile_version,
        fields=[_field("person.full_name", "After", edited)],
        user_confirmed=True,
    )

    values = {field.id: field.value for field in updated.fields}
    assert values == {"person.full_name": "After", "contact.email": "person@example.invalid"}
    assert updated.profile_version == 2
    assert updated.created_at == initial.created_at
    assert updated.updated_at == edited


def test_invalid_input_does_not_replace_last_valid_snapshot(
    fake_profile_store: ProfileStore,
) -> None:
    timestamp = datetime(2099, 3, 1, tzinfo=UTC)
    service = _service(fake_profile_store, timestamp, timestamp)
    saved = service.upsert(
        PROFILE_ID,
        expected_profile_version=0,
        fields=[_field("person.full_name", "Valid", timestamp)],
        user_confirmed=True,
    )

    with pytest.raises(InvalidFieldValueError):
        service.upsert(
            PROFILE_ID,
            expected_profile_version=saved.profile_version,
            fields=[_field("person.full_name", "   ", timestamp)],
            user_confirmed=True,
        )

    assert service.read(PROFILE_ID).to_dict() == saved.to_dict()
    assert fake_profile_store.write_calls == 1


def test_cancel_is_non_mutating_and_returns_current_snapshot(
    fake_profile_store: ProfileStore,
) -> None:
    timestamp = datetime(2099, 4, 1, tzinfo=UTC)
    service = _service(fake_profile_store, timestamp)
    saved = service.upsert(
        PROFILE_ID,
        expected_profile_version=0,
        fields=[_field("person.full_name", "Saved", timestamp)],
        user_confirmed=True,
    )
    writes_before = fake_profile_store.write_calls

    cancelled = service.cancel(PROFILE_ID)

    assert cancelled.to_dict() == saved.to_dict()
    assert fake_profile_store.write_calls == writes_before


def test_stale_version_is_rejected_without_write(fake_profile_store: ProfileStore) -> None:
    timestamp = datetime(2099, 5, 1, tzinfo=UTC)
    service = _service(fake_profile_store, timestamp)
    saved = service.upsert(
        PROFILE_ID,
        expected_profile_version=0,
        fields=[_field("person.full_name", "Saved", timestamp)],
        user_confirmed=True,
    )
    writes_before = fake_profile_store.write_calls

    with pytest.raises(StaleProfileVersionError):
        service.upsert(
            PROFILE_ID,
            expected_profile_version=saved.profile_version - 1,
            fields=[_field("person.full_name", "Stale", timestamp)],
            user_confirmed=True,
        )

    assert fake_profile_store.write_calls == writes_before


def test_unconfirmed_mutation_is_rejected_without_write(fake_profile_store: ProfileStore) -> None:
    timestamp = datetime(2099, 6, 1, tzinfo=UTC)
    service = _service(fake_profile_store, timestamp)

    with pytest.raises(ConfirmationRequiredError):
        service.upsert(
            PROFILE_ID,
            expected_profile_version=0,
            fields=[_field("person.full_name", "Candidate", timestamp)],
            user_confirmed=False,
        )

    assert fake_profile_store.write_calls == 0

