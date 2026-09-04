"""Regression tests for preserving independent values in multiple scopes."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from resume_agent.profile.errors import InvalidFieldValueError
from resume_agent.profile.models import (
    CustomFieldDefinition,
    FieldType,
    PageOption,
    Scope,
    Sensitivity,
)
from resume_agent.profile.service import ProfileService
from resume_agent.storage.base import ProfileStore

PROFILE_ID = "profile-custom-scopes"
STAMP = datetime(2099, 1, 1, tzinfo=UTC)


def _definition() -> CustomFieldDefinition:
    options = [
        PageOption(value="beijing", label="北京"),
        PageOption(value="shanghai", label="上海"),
    ]
    return CustomFieldDefinition(
        id="custom.scope-aware",
        label="Scope-aware city",
        field_type=FieldType.ENUM,
        default_sensitivity=Sensitivity.NORMAL,
        requires_confirmation=True,
        is_custom=True,
        allowed_scopes=[Scope.GLOBAL, Scope.WEBSITE],
        options=options,
        created_at=STAMP,
        updated_at=STAMP,
    )


def test_updating_one_scope_does_not_remove_other_scope_value(
    fake_profile_store: ProfileStore,
) -> None:
    service = ProfileService(fake_profile_store, profile_id=PROFILE_ID)
    definition = _definition()
    created = service.create_custom_field(
        PROFILE_ID,
        expected_profile_version=0,
        definition=definition,
        value="beijing",
        scope=Scope.GLOBAL,
        user_confirmed=True,
    )

    website_value = service.update_custom_field(
        PROFILE_ID,
        expected_profile_version=created.profile_version,
        field_id=definition.id,
        value="shanghai",
        scope=Scope.WEBSITE,
        scope_context="jobs.example.invalid",
        user_confirmed=True,
    )

    values = {(field.scope, field.scope_context): field.value for field in website_value.fields}
    assert values == {
        (Scope.GLOBAL, None): "beijing",
        (Scope.WEBSITE, "jobs.example.invalid"): "shanghai",
    }

    global_value = service.update_custom_field(
        PROFILE_ID,
        expected_profile_version=website_value.profile_version,
        field_id=definition.id,
        value="shanghai",
        scope=Scope.GLOBAL,
        user_confirmed=True,
    )
    values = {(field.scope, field.scope_context): field.value for field in global_value.fields}
    assert values == {
        (Scope.GLOBAL, None): "shanghai",
        (Scope.WEBSITE, "jobs.example.invalid"): "shanghai",
    }


def test_update_without_scope_rejects_ambiguous_existing_values(
    fake_profile_store: ProfileStore,
) -> None:
    service = ProfileService(fake_profile_store, profile_id=PROFILE_ID)
    definition = _definition()
    created = service.create_custom_field(
        PROFILE_ID,
        expected_profile_version=0,
        definition=definition,
        value="beijing",
        scope=Scope.GLOBAL,
        user_confirmed=True,
    )
    with_website = service.update_custom_field(
        PROFILE_ID,
        expected_profile_version=created.profile_version,
        field_id=definition.id,
        value="shanghai",
        scope=Scope.WEBSITE,
        scope_context="jobs.example.invalid",
        user_confirmed=True,
    )
    writes_before = fake_profile_store.write_calls

    with pytest.raises(InvalidFieldValueError) as caught:
        service.update_custom_field(
            PROFILE_ID,
            expected_profile_version=with_website.profile_version,
            field_id=definition.id,
            value="beijing",
            user_confirmed=True,
        )

    assert caught.value.details["reason"] == "ambiguous_scope"
    assert fake_profile_store.write_calls == writes_before


def test_update_replaces_only_matching_scope_context(
    fake_profile_store: ProfileStore,
) -> None:
    service = ProfileService(fake_profile_store, profile_id=PROFILE_ID)
    definition = _definition()
    created = service.create_custom_field(
        PROFILE_ID,
        expected_profile_version=0,
        definition=definition,
        value="beijing",
        scope=Scope.GLOBAL,
        user_confirmed=True,
    )
    first_website = service.update_custom_field(
        PROFILE_ID,
        expected_profile_version=created.profile_version,
        field_id=definition.id,
        value="shanghai",
        scope=Scope.WEBSITE,
        scope_context="jobs.example.invalid",
        user_confirmed=True,
    )
    second_website = service.update_custom_field(
        PROFILE_ID,
        expected_profile_version=first_website.profile_version,
        field_id=definition.id,
        value="beijing",
        scope=Scope.WEBSITE,
        scope_context="other.example.invalid",
        user_confirmed=True,
    )

    updated = service.update_custom_field(
        PROFILE_ID,
        expected_profile_version=second_website.profile_version,
        field_id=definition.id,
        value="shanghai",
        scope=Scope.WEBSITE,
        scope_context="jobs.example.invalid",
        user_confirmed=True,
    )

    values = {(field.scope, field.scope_context): field.value for field in updated.fields}
    assert values == {
        (Scope.GLOBAL, None): "beijing",
        (Scope.WEBSITE, "jobs.example.invalid"): "shanghai",
        (Scope.WEBSITE, "other.example.invalid"): "beijing",
    }
