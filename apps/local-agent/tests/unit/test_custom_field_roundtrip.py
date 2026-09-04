"""Regression tests for custom-definition JSON round trips."""

from __future__ import annotations

from datetime import UTC, datetime

from resume_agent.profile.models import CustomFieldDefinition, FieldType, Scope, Sensitivity
from resume_agent.profile.service import ProfileService

PROFILE_ID = "profile-synthetic-f001-roundtrip"
CREATED = datetime(2099, 1, 1, tzinfo=UTC)


class _JsonRoundTripStore:
    """Store fake that serializes every write like the encrypted JSON store."""

    def __init__(self) -> None:
        self.snapshot: dict[str, object] | None = None

    def read(self) -> dict[str, object] | None:
        return self.snapshot

    def write(self, snapshot: object) -> None:
        self.snapshot = snapshot.to_dict()  # type: ignore[union-attr]

    def delete(self) -> None:
        self.snapshot = None


def _definition(field_id: str) -> CustomFieldDefinition:
    return CustomFieldDefinition(
        id=field_id,
        label="可接受城市",
        field_type=FieldType.TEXT,
        default_sensitivity=Sensitivity.NORMAL,
        requires_confirmation=True,
        is_custom=True,
        allowed_scopes=[Scope.GLOBAL],
        created_at=CREATED,
        updated_at=CREATED,
    )


def _service(store: _JsonRoundTripStore) -> ProfileService:
    return ProfileService(store, profile_id=PROFILE_ID)  # type: ignore[arg-type]


def test_ordinary_upsert_preserves_custom_value_marker_after_json_round_trip() -> None:
    """Editing a custom value through regular upsert keeps its custom marker."""

    store = _JsonRoundTripStore()
    service = _service(store)
    definition = _definition("custom.upsert-city")
    created = service.create_custom_field(
        PROFILE_ID,
        expected_profile_version=0,
        definition=definition,
        value="beijing",
        scope=Scope.GLOBAL,
        user_confirmed=True,
    )

    restarted = _service(store)
    updated = restarted.upsert(
        PROFILE_ID,
        expected_profile_version=created.profile_version,
        fields=[
            {
                "id": definition.id,
                "value": "shanghai",
                "confirmed": True,
                "source": {"kind": "manual"},
            }
        ],
        user_confirmed=True,
    )

    value = next(item for item in updated.fields if item.id == definition.id)
    assert value.value == "shanghai"
    assert value.is_custom is True
