"""Regression tests for subtype preservation across encrypted-snapshot decoding."""

from __future__ import annotations

from datetime import UTC, datetime

from resume_agent.profile.models import (
    CustomFieldDefinition,
    FieldType,
    ProfileSnapshot,
    Scope,
    Sensitivity,
)
from resume_agent.profile.service import ProfileService
from resume_agent.storage.base import ProfileStore

PROFILE_ID = "profile-roundtrip-subtypes"
STAMP = datetime(2099, 1, 1, tzinfo=UTC)


class JsonRoundTripStore:
    """A deterministic stand-in for an encrypted store's JSON decode boundary."""

    def __init__(self) -> None:
        self.payload: str | None = None

    def read(self) -> ProfileSnapshot | None:
        return ProfileSnapshot.from_json(self.payload) if self.payload is not None else None

    def write(self, snapshot: ProfileSnapshot) -> None:
        self.payload = snapshot.to_json()

    def delete(self) -> None:
        self.payload = None


def _definition() -> CustomFieldDefinition:
    return CustomFieldDefinition(
        id="custom.roundtrip",
        label="Roundtrip field",
        field_type=FieldType.TEXT,
        default_sensitivity=Sensitivity.NORMAL,
        requires_confirmation=True,
        is_custom=True,
        allowed_scopes=[Scope.GLOBAL],
        created_at=STAMP,
        updated_at=STAMP,
    )


def test_custom_definition_remains_editable_after_json_roundtrip() -> None:
    store: ProfileStore = JsonRoundTripStore()
    first_service = ProfileService(store, profile_id=PROFILE_ID)
    created = first_service.create_custom_field(
        PROFILE_ID,
        expected_profile_version=0,
        definition=_definition(),
        value="before",
        scope=Scope.GLOBAL,
        user_confirmed=True,
    )

    decoded = store.read()
    assert decoded is not None
    assert isinstance(decoded.field_definitions[-1], CustomFieldDefinition)

    restarted_service = ProfileService(store, profile_id=PROFILE_ID)
    updated = restarted_service.update_custom_field(
        PROFILE_ID,
        expected_profile_version=created.profile_version,
        field_id="custom.roundtrip",
        value="after",
        user_confirmed=True,
    )

    assert (
        next(field for field in updated.fields if field.id == "custom.roundtrip").value == "after"
    )
    assert (
        next(field for field in updated.fields if field.id == "custom.roundtrip").is_custom is True
    )
