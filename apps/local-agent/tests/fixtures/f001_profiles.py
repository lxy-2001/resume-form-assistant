"""Reusable, deterministic synthetic profiles for F001 tests.

The builders intentionally return plain dictionaries so tests can use them before domain models
are implemented. They are not a copy of the shared contract schema.
"""

from copy import deepcopy
from typing import Any

PROFILE_ID = "profile-synthetic-f001-001"


def build_profile(*, include_sensitive: bool = True, include_records: bool = True) -> dict[str, Any]:
    """Build a representative ordinary F001 profile snapshot."""
    profile: dict[str, Any] = {
        "profile_id": PROFILE_ID,
        "profile_version": 1,
        "fields": {
            "full_name": {"value": "Synthetic Test Person", "sensitivity": "normal"},
            "email": {"value": "synthetic.person@example.invalid", "sensitivity": "normal"},
            "city": {"value": "Example City", "sensitivity": "normal"},
            "graduation_date": {"value": "2099-12-31", "sensitivity": "normal"},
        },
        "custom_fields": [
            {
                "field_id": "custom.synthetic-track",
                "label": "Synthetic Track",
                "type": "enum",
                "options": ["alpha", "beta"],
                "value": "alpha",
                "sensitivity": "normal",
                "scope": "global",
            }
        ],
        "records": [],
    }
    if include_sensitive:
        profile["fields"]["government_id"] = {
            "value": "SYNTHETIC-ID-NOT-VALID",
            "sensitivity": "highly_sensitive",
            "requires_confirmation": True,
        }
    if include_records:
        profile["records"] = [
            {"record_id": "edu-synthetic-001", "record_type": "education", "school": "Synthetic University", "degree": "Example Degree", "start_date": "2095-09-01", "end_date": "2099-06-30"},
            {"record_id": "work-synthetic-001", "record_type": "work", "employer": "Synthetic Labs", "title": "Example Intern", "start_date": "2098-07-01", "end_date": "2098-09-30"},
            {"record_id": "project-synthetic-001", "record_type": "project", "name": "Example Project", "description": "Synthetic project description for tests.", "role": "Example Contributor"},
        ]
    return profile


def build_empty_profile() -> dict[str, Any]:
    return {"profile_id": PROFILE_ID, "profile_version": 0, "is_empty": True, "fields": {}, "records": [], "custom_fields": []}


def build_invalid_candidates() -> list[dict[str, Any]]:
    """Return deterministic candidates useful for validation tests."""
    return [
        {"field_id": "email", "value": "not-an-email", "sensitivity": "normal"},
        {"field_id": "graduation_date", "value": "2099-99-99", "sensitivity": "normal"},
        {"field_id": "government_id", "value": "SYNTHETIC-ID-NOT-VALID", "sensitivity": "highly_sensitive", "requires_confirmation": False},
    ]


def clone_profile(profile: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return an independent copy for mutation/conflict tests."""
    return deepcopy(profile if profile is not None else build_profile())


# Explicit pytest fixtures remain optional: importing this module never requires pytest.
try:  # pragma: no cover - exercised by pytest collection when pytest is installed
    import pytest

    @pytest.fixture
    def synthetic_profile() -> dict[str, Any]:
        return build_profile()

    @pytest.fixture
    def empty_synthetic_profile() -> dict[str, Any]:
        return build_empty_profile()
except ImportError:  # pragma: no cover
    pass
