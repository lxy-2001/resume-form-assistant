"""T027 RED tests for confirmed, typed custom-field lifecycle operations."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from resume_agent.profile.errors import (
    ConfirmationRequiredError,
    CustomFieldConflictError,
    InvalidFieldValueError,
)
from resume_agent.profile.models import (
    CustomFieldDefinition,
    FieldType,
    PageOption,
    Scope,
    Sensitivity,
    ValidationRule,
)
from resume_agent.profile.service import ProfileService
from resume_agent.storage.base import ProfileStore

PROFILE_ID = "profile-synthetic-f001-001"
CREATED = datetime(2099, 1, 1, tzinfo=UTC)
EDITED = datetime(2099, 1, 2, tzinfo=UTC)


def _definition(
    field_id: str = "custom.acceptable-city",
    *,
    label: str = "可接受城市",
    field_type: FieldType = FieldType.ENUM,
    options: list[PageOption] | None = None,
    sensitivity: Sensitivity = Sensitivity.NORMAL,
    scopes: list[Scope] | None = None,
    requires_confirmation: bool = False,
) -> CustomFieldDefinition:
    if options is None and field_type in {FieldType.ENUM, FieldType.MULTIVALUE}:
        options = [
            PageOption(value="beijing", label="北京"),
            PageOption(value="shanghai", label="上海"),
        ]
    return CustomFieldDefinition(
        id=field_id,
        label=label,
        field_type=field_type,
        default_sensitivity=sensitivity,
        requires_confirmation=requires_confirmation,
        is_custom=True,
        allowed_scopes=scopes or [Scope.GLOBAL],
        options=options,
        validation=ValidationRule(allowed_values=[option.value for option in options])
        if options is not None
        else None,
        created_at=CREATED,
        updated_at=EDITED,
    )


def _service(store: ProfileStore) -> ProfileService:
    return ProfileService(store, profile_id=PROFILE_ID)


def test_create_custom_enum_field_persists_definition_value_and_scope(
    fake_profile_store: ProfileStore,
) -> None:
    definition = _definition()
    service = _service(fake_profile_store)

    snapshot = service.create_custom_field(
        PROFILE_ID,
        expected_profile_version=0,
        definition=definition,
        value="beijing",
        scope=Scope.GLOBAL,
        user_confirmed=True,
    )

    stored_definition = next(
        item for item in snapshot.field_definitions if item.id == definition.id
    )
    stored_value = next(item for item in snapshot.fields if item.id == definition.id)
    assert stored_definition.is_custom is True
    assert stored_definition.field_type is FieldType.ENUM
    assert [option.value for option in (stored_definition.options or [])] == ["beijing", "shanghai"]
    assert stored_value.value == "beijing"
    assert stored_value.scope is Scope.GLOBAL
    assert stored_value.is_custom is True
    assert stored_value.confirmed is True


@pytest.mark.parametrize(
    ("field_type", "valid_value", "invalid_value"),
    [
        (FieldType.ENUM, "beijing", "guangzhou"),
        (FieldType.MULTIVALUE, ["beijing", "shanghai"], ["beijing", "guangzhou"]),
        (FieldType.BOOLEAN, True, "true"),
    ],
)
def test_custom_field_types_reject_invalid_values_without_replacing_valid_value(
    fake_profile_store: ProfileStore,
    field_type: FieldType,
    valid_value: object,
    invalid_value: object,
) -> None:
    definition = _definition(field_id=f"custom.typed-{field_type.value}", field_type=field_type)
    service = _service(fake_profile_store)
    saved = service.create_custom_field(
        PROFILE_ID,
        expected_profile_version=0,
        definition=definition,
        value=valid_value,
        scope=Scope.GLOBAL,
        user_confirmed=True,
    )
    writes_before_invalid = fake_profile_store.write_calls

    with pytest.raises(InvalidFieldValueError):
        service.update_custom_field(
            PROFILE_ID,
            expected_profile_version=saved.profile_version,
            field_id=definition.id,
            value=invalid_value,
            user_confirmed=True,
        )

    current = service.read(PROFILE_ID)
    stored_value = next(item for item in current.fields if item.id == definition.id)
    assert stored_value.value == valid_value
    assert fake_profile_store.write_calls == writes_before_invalid


def test_custom_field_scope_and_sensitive_level_are_explicit_and_confirmed(
    fake_profile_store: ProfileStore,
) -> None:
    definition = _definition(
        field_id="custom.preferred-city",
        sensitivity=Sensitivity.SENSITIVE,
        scopes=[Scope.WEBSITE],
        requires_confirmation=True,
    )
    service = _service(fake_profile_store)

    snapshot = service.create_custom_field(
        PROFILE_ID,
        expected_profile_version=0,
        definition=definition,
        value="beijing",
        scope=Scope.WEBSITE,
        scope_context="jobs.example.invalid",
        user_confirmed=True,
    )

    value = next(item for item in snapshot.fields if item.id == definition.id)
    assert value.scope is Scope.WEBSITE
    assert value.scope_context == "jobs.example.invalid"
    assert value.sensitivity is Sensitivity.SENSITIVE
    assert value.requires_confirmation is True
    assert value.confirmed is True


@pytest.mark.parametrize(
    ("field_id", "label"),
    [
        ("person.full_name", "其他名称"),
        ("custom.shadow-name", "姓名"),
        ("custom.shadow-name-with-space", " 姓名 "),
        ("custom.shadow-name-alias", "NAME"),
        ("name", "其他字段"),
    ],
)
def test_custom_field_id_or_label_cannot_conflict_with_standard_catalog(
    fake_profile_store: ProfileStore,
    field_id: str,
    label: str,
) -> None:
    service = _service(fake_profile_store)
    definition = _definition(
        field_id=field_id, label=label, field_type=FieldType.TEXT, options=None
    )

    with pytest.raises(CustomFieldConflictError):
        service.create_custom_field(
            PROFILE_ID,
            expected_profile_version=0,
            definition=definition,
            value="Synthetic value",
            scope=Scope.GLOBAL,
            user_confirmed=True,
        )

    assert fake_profile_store.write_calls == 0
    assert not any(
        item.id == field_id and item.is_custom
        for item in service.read(PROFILE_ID).field_definitions
    )


def test_custom_field_creation_cancelled_before_confirmation_has_no_permanent_definition(
    fake_profile_store: ProfileStore,
) -> None:
    service = _service(fake_profile_store)
    definition = _definition()

    with pytest.raises(ConfirmationRequiredError):
        service.create_custom_field(
            PROFILE_ID,
            expected_profile_version=0,
            definition=definition,
            value="beijing",
            scope=Scope.GLOBAL,
            user_confirmed=False,
        )

    current = service.read(PROFILE_ID)
    assert not any(item.is_custom for item in current.field_definitions)
    assert current.fields == []
    assert fake_profile_store.write_calls == 0


def test_upsert_updates_existing_custom_definition_and_preserves_stable_id(
    fake_profile_store: ProfileStore,
) -> None:
    service = _service(fake_profile_store)
    definition = _definition(field_id="custom.editable-city")
    created = service.create_custom_field(
        PROFILE_ID,
        expected_profile_version=0,
        definition=definition,
        value="beijing",
        scope=Scope.GLOBAL,
        user_confirmed=True,
    )
    revised = definition.model_copy(update={"label": "可接受城市（更新）"})

    updated = service.upsert_extended(
        PROFILE_ID,
        expected_profile_version=created.profile_version,
        custom_field_definitions=[revised],
        user_confirmed=True,
    )

    stored_definition = next(item for item in updated.field_definitions if item.id == definition.id)
    stored_value = next(item for item in updated.fields if item.id == definition.id)
    assert stored_definition.label == "可接受城市（更新）"
    assert stored_definition.created_at == definition.created_at
    assert stored_value.label == "可接受城市（更新）"
    assert stored_value.options == revised.options


def test_custom_definition_update_rejects_incompatible_existing_value_without_write(
    fake_profile_store: ProfileStore,
) -> None:
    service = _service(fake_profile_store)
    definition = _definition(field_id="custom.incompatible-city")
    created = service.create_custom_field(
        PROFILE_ID,
        expected_profile_version=0,
        definition=definition,
        value="beijing",
        scope=Scope.GLOBAL,
        user_confirmed=True,
    )
    revised = definition.model_copy(
        update={
            "options": [PageOption(value="shanghai", label="上海")],
            "validation": ValidationRule(allowed_values=["shanghai"]),
        }
    )
    writes_before = fake_profile_store.write_calls

    with pytest.raises(InvalidFieldValueError):
        service.upsert_extended(
            PROFILE_ID,
            expected_profile_version=created.profile_version,
            custom_field_definitions=[revised],
            user_confirmed=True,
        )

    assert fake_profile_store.write_calls == writes_before
    assert (
        next(item for item in service.read(PROFILE_ID).fields if item.id == definition.id).value
        == "beijing"
    )


def test_custom_definition_update_rejects_existing_label_or_alias_conflict(
    fake_profile_store: ProfileStore,
) -> None:
    service = _service(fake_profile_store)
    first = _definition(field_id="custom.first-city", label="首选城市")
    second = _definition(field_id="custom.second-city", label="备选城市")
    created = service.create_custom_field(
        PROFILE_ID,
        expected_profile_version=0,
        definition=first,
        value="beijing",
        scope=Scope.GLOBAL,
        user_confirmed=True,
    )
    created = service.create_custom_field(
        PROFILE_ID,
        expected_profile_version=created.profile_version,
        definition=second,
        value="shanghai",
        scope=Scope.GLOBAL,
        user_confirmed=True,
    )
    writes_before = fake_profile_store.write_calls

    with pytest.raises(CustomFieldConflictError):
        service.upsert_extended(
            PROFILE_ID,
            expected_profile_version=created.profile_version,
            custom_field_definitions=[first.model_copy(update={"label": " 备选城市 "})],
            user_confirmed=True,
        )

    assert fake_profile_store.write_calls == writes_before


def test_upsert_extended_rejects_duplicate_field_values_in_one_bundle(
    fake_profile_store: ProfileStore,
) -> None:
    service = _service(fake_profile_store)
    field = {
        "id": "person.full_name",
        "value": "Synthetic Person",
        "scope": Scope.GLOBAL,
        "confirmed": True,
        "source": {"kind": "manual"},
    }

    with pytest.raises(InvalidFieldValueError) as caught:
        service.upsert_extended(
            PROFILE_ID,
            expected_profile_version=0,
            fields=[field, dict(field)],
            user_confirmed=True,
        )

    assert caught.value.details.get("reason") == "duplicate_field"
    assert fake_profile_store.write_calls == 0


def test_upsert_extended_rejects_duplicate_definition_ids_in_one_bundle(
    fake_profile_store: ProfileStore,
) -> None:
    service = _service(fake_profile_store)
    definition = _definition(field_id="custom.duplicate-definition")

    with pytest.raises(InvalidFieldValueError) as caught:
        service.upsert_extended(
            PROFILE_ID,
            expected_profile_version=0,
            custom_field_definitions=[definition, definition.model_copy(deep=True)],
            user_confirmed=True,
        )

    assert caught.value.details.get("reason") == "duplicate_definition"
    assert fake_profile_store.write_calls == 0


def test_upsert_extended_rejects_colliding_new_definition_labels_in_one_bundle(
    fake_profile_store: ProfileStore,
) -> None:
    service = _service(fake_profile_store)
    first = _definition(field_id="custom.first-batch", label="批次字段一")
    second = _definition(field_id="custom.second-batch", label=" 批次字段一 ")

    with pytest.raises(CustomFieldConflictError):
        service.upsert_extended(
            PROFILE_ID,
            expected_profile_version=0,
            custom_field_definitions=[first, second],
            user_confirmed=True,
        )

    assert fake_profile_store.write_calls == 0
