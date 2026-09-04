"""T026 RED tests for isolated repeatable-record lifecycle operations.

These tests deliberately define the service seam for US2 before its implementation exists.  All
data is synthetic and uses the in-memory ``fake_profile_store`` fixture, so the tests cannot touch
the user's encrypted profile or a network service.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from resume_agent.profile.errors import ConfirmationRequiredError, StaleProfileVersionError
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
from resume_agent.storage.base import ProfileStore

PROFILE_ID = "profile-synthetic-f001-001"
CREATED = datetime(2099, 1, 1, tzinfo=UTC)
EDITED = datetime(2099, 1, 2, tzinfo=UTC)


def _field(field_id: str, value: object, *, updated_at: datetime = CREATED) -> FieldValue:
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
        updated_at=updated_at,
    )


def _record(
    record_id: str,
    record_type: ProfileRecordType,
    position: int,
    *,
    school_or_project: str,
    updated_at: datetime = CREATED,
) -> RepeatableRecord:
    field_id = (
        "education.school_name"
        if record_type is ProfileRecordType.EDUCATION
        else "experience.organization"
    )
    return RepeatableRecord(
        record_id=record_id,
        record_type=record_type,
        position=position,
        fields=[_field(field_id, school_or_project, updated_at=updated_at)],
        confirmed=True,
        created_at=CREATED,
        updated_at=updated_at,
    )


def _service(store: ProfileStore) -> ProfileService:
    return ProfileService(store, profile_id=PROFILE_ID)


def test_records_are_independent_when_added_and_one_is_edited(
    fake_profile_store: ProfileStore,
) -> None:
    """Editing one education record must not mutate a sibling record."""

    service = _service(fake_profile_store)
    first = _record(
        "education-synthetic-001",
        ProfileRecordType.EDUCATION,
        0,
        school_or_project="Synthetic University",
    )
    second = _record(
        "education-synthetic-002",
        ProfileRecordType.EDUCATION,
        1,
        school_or_project="Example College",
    )

    after_first = service.upsert_record(
        PROFILE_ID,
        expected_profile_version=0,
        record=first,
        user_confirmed=True,
    )
    after_second = service.upsert_record(
        PROFILE_ID,
        expected_profile_version=after_first.profile_version,
        record=second,
        user_confirmed=True,
    )
    edited_first = first.model_copy(
        deep=True,
        update={
            "fields": [_field("education.school_name", "Updated University", updated_at=EDITED)]
        },
    )

    result = service.upsert_record(
        PROFILE_ID,
        expected_profile_version=after_second.profile_version,
        record=edited_first,
        user_confirmed=True,
    )

    by_id = {record.record_id: record for record in result.records}
    assert set(by_id) == {first.record_id, second.record_id}
    assert by_id[first.record_id].fields[0].value == "Updated University"
    assert by_id[second.record_id].fields[0].value == "Example College"
    assert result.profile_version == after_second.profile_version + 1


def test_reorder_records_assigns_stable_positions_without_changing_record_ids(
    fake_profile_store: ProfileStore,
) -> None:
    """Reordering is explicit and keeps each record's stable identity and fields."""

    service = _service(fake_profile_store)
    first = _record(
        "education-synthetic-001",
        ProfileRecordType.EDUCATION,
        0,
        school_or_project="Synthetic University",
    )
    second = _record(
        "project-synthetic-001",
        ProfileRecordType.PROJECT,
        1,
        school_or_project="Synthetic Project",
    )
    current = service.upsert_record(
        PROFILE_ID,
        expected_profile_version=0,
        record=first,
        user_confirmed=True,
    )
    current = service.upsert_record(
        PROFILE_ID,
        expected_profile_version=current.profile_version,
        record=second,
        user_confirmed=True,
    )

    reordered = service.reorder_records(
        PROFILE_ID,
        expected_profile_version=current.profile_version,
        ordered_record_ids=[second.record_id, first.record_id],
        user_confirmed=True,
    )

    assert [record.record_id for record in reordered.records] == [second.record_id, first.record_id]
    assert [record.position for record in reordered.records] == [0, 1]
    assert reordered.records[0].fields[0].value == "Synthetic Project"
    assert reordered.records[1].fields[0].value == "Synthetic University"


def test_deleting_one_record_leaves_other_records_untouched(
    fake_profile_store: ProfileStore,
) -> None:
    """A confirmed single-record deletion must not delete or renumber its sibling."""

    service = _service(fake_profile_store)
    first = _record(
        "education-synthetic-001",
        ProfileRecordType.EDUCATION,
        0,
        school_or_project="Synthetic University",
    )
    second = _record(
        "education-synthetic-002",
        ProfileRecordType.EDUCATION,
        1,
        school_or_project="Example College",
    )
    current = service.upsert_record(
        PROFILE_ID,
        expected_profile_version=0,
        record=first,
        user_confirmed=True,
    )
    current = service.upsert_record(
        PROFILE_ID,
        expected_profile_version=current.profile_version,
        record=second,
        user_confirmed=True,
    )
    writes_before_delete = fake_profile_store.write_calls

    deleted = service.delete_record(
        PROFILE_ID,
        expected_profile_version=current.profile_version,
        record_id=first.record_id,
        user_confirmed=True,
    )

    assert [record.record_id for record in deleted.records] == [second.record_id]
    assert deleted.records[0].position == second.position
    assert deleted.records[0].fields[0].value == "Example College"
    assert fake_profile_store.write_calls == writes_before_delete + 1


def test_record_mutations_require_confirmation_and_current_version(
    fake_profile_store: ProfileStore,
) -> None:
    """Unconfirmed or stale record mutations fail before writing a new snapshot."""

    service = _service(fake_profile_store)
    record = _record(
        "education-synthetic-001",
        ProfileRecordType.EDUCATION,
        0,
        school_or_project="Synthetic University",
    )

    with pytest.raises(ConfirmationRequiredError):
        service.upsert_record(
            PROFILE_ID,
            expected_profile_version=0,
            record=record,
            user_confirmed=False,
        )
    assert fake_profile_store.write_calls == 0

    saved = service.upsert_record(
        PROFILE_ID,
        expected_profile_version=0,
        record=record,
        user_confirmed=True,
    )
    writes_before_stale = fake_profile_store.write_calls
    with pytest.raises(StaleProfileVersionError):
        service.delete_record(
            PROFILE_ID,
            expected_profile_version=saved.profile_version - 1,
            record_id=record.record_id,
            user_confirmed=True,
        )
    assert fake_profile_store.write_calls == writes_before_stale
