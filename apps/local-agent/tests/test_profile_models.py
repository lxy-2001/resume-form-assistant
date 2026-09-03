from datetime import UTC, datetime

import pytest

from resume_agent.profile.models import (
    CustomFieldDefinition,
    FieldType,
    FieldValue,
    ProfileRecordType,
    ProfileSnapshot,
    Scope,
    Sensitivity,
    Source,
)

TS = datetime(2099, 1, 1, tzinfo=UTC)


def _field(**overrides: object) -> FieldValue:
    data: dict[str, object] = {
        "field_id": "email",
        "label": "Email",
        "field_type": FieldType.EMAIL,
        "value": "person@example.invalid",
        "scope": Scope.GLOBAL,
        "sensitivity": Sensitivity.NORMAL,
        "requires_confirmation": False,
        "confirmed": True,
        "source": Source(kind="manual"),
        "updated_at": TS,
    }
    data.update(overrides)
    return FieldValue.model_validate(data)


def test_sensitive_values_require_confirmation() -> None:
    with pytest.raises(ValueError):
        _field(sensitivity=Sensitivity.SENSITIVE, requires_confirmation=False)


def test_scope_context_is_required_only_for_scoped_values() -> None:
    with pytest.raises(ValueError):
        _field(scope=Scope.WEBSITE)
    with pytest.raises(ValueError):
        _field(scope=Scope.GLOBAL, scope_context="site.example")


def test_snapshot_distinguishes_empty_and_non_empty_and_roundtrips() -> None:
    empty = ProfileSnapshot(
        profile_id="profile-1", profile_version=0, fields=[], records=[], field_definitions=[], created_at=TS, updated_at=TS
    )
    assert empty.is_empty is True
    value = _field()
    snapshot = ProfileSnapshot(
        profile_id="profile-1", profile_version=1, fields=[value], records=[], field_definitions=[], created_at=TS, updated_at=TS
    )
    assert snapshot.is_empty is False
    assert ProfileSnapshot.from_json(snapshot.to_json()) == snapshot


def test_confirmed_record_requires_a_field_and_unknown_properties_are_rejected() -> None:
    with pytest.raises(ValueError):
        ProfileSnapshot(
            profile_id="profile-1", profile_version=1, fields=[], records=[{
                "record_id": "r1", "record_type": ProfileRecordType.WORK, "position": 0,
                "fields": [], "confirmed": True, "created_at": TS, "updated_at": TS,
            }], field_definitions=[], created_at=TS, updated_at=TS
        )
    with pytest.raises(ValueError):
        CustomFieldDefinition(id="custom-x", label="X", field_type=FieldType.TEXT,
                              default_sensitivity=Sensitivity.NORMAL, requires_confirmation=False,
                              is_custom=True, allowed_scopes=[Scope.GLOBAL], created_at=TS,
                              updated_at=TS, unexpected="nope")

def test_field_value_roundtrips_contract_metadata() -> None:
    value = _field(id="email", is_custom=False, aliases=["邮箱"], options=None,
                   validation={"format": "email"})
    data = value.to_dict()
    assert data["id"] == "email"
    assert data["field_id"] == "email"
    assert data["is_custom"] is False
    assert ProfileSnapshot.from_json(ProfileSnapshot(profile_id="p", profile_version=1, fields=[value], records=[], field_definitions=[], created_at=TS, updated_at=TS).to_json()).fields[0].id == "email"


def test_validation_rule_rejects_unknown_format() -> None:
    with pytest.raises(ValueError):
        from resume_agent.profile.models import ValidationRule
        ValidationRule(format="unknown")


def test_definition_subclasses_reject_conflicting_custom_flag() -> None:
    with pytest.raises(ValueError):
        from resume_agent.profile.models import StandardFieldDefinition
        StandardFieldDefinition(id="std", label="Std", field_type=FieldType.TEXT,
                                default_sensitivity=Sensitivity.NORMAL, requires_confirmation=False,
                                is_custom=True, allowed_scopes=[Scope.GLOBAL])

