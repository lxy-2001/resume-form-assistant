"""Focused checks for the shared, offline F001 test fixtures.

These tests intentionally exercise only the test seams.  They must never touch a
real keyring, network, or a profile outside pytest's temporary directory.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from resume_agent.config import AppConfig
from resume_agent.profile.models import ProfileSnapshot
from resume_agent.storage.base import AtomicWriter, ProfileStore
from resume_agent.storage.key_provider import KeyProvider


def test_temp_root_and_config_are_isolated_and_side_effect_free(
    data_root: Path,
    app_config: AppConfig,
) -> None:
    """The root is a fresh pytest directory and config construction creates no profile."""

    assert data_root.is_absolute()
    assert app_config.data_root == data_root
    assert data_root.exists()
    assert list(data_root.iterdir()) == []

    (data_root / "synthetic-marker").write_text("fixture-only", encoding="utf-8")
    assert app_config.profile_path() == data_root / "profile.json"
    assert not app_config.profile_path().exists()


def test_temp_root_starts_fresh_for_each_test(data_root: Path) -> None:
    """A previous test's marker must not leak into another fixture instance."""

    assert not (data_root / "synthetic-marker").exists()


def test_synthetic_profile_fixture_is_independent(synthetic_profile: dict[str, object]) -> None:
    """The conftest wrapper returns a new copy, preserving the builder's public data."""

    assert synthetic_profile["profile_id"] == "profile-synthetic-f001-001"
    fields = synthetic_profile["fields"]
    assert isinstance(fields, dict)
    assert fields["email"]["value"].endswith(".invalid")  # type: ignore[index]
    assert "Synthetic" in str(fields["full_name"])  # type: ignore[index]

    fields["full_name"]["value"] = "changed in one test"  # type: ignore[index]


def test_synthetic_profile_fixture_does_not_share_mutations(
    synthetic_profile: dict[str, object],
) -> None:
    fields = synthetic_profile["fields"]
    assert isinstance(fields, dict)
    assert fields["full_name"]["value"] == "Synthetic Test Person"  # type: ignore[index]


def test_fake_key_provider_is_protocol_conformant_and_in_memory(
    fake_key_provider: KeyProvider,
) -> None:
    assert isinstance(fake_key_provider, KeyProvider)
    provider = fake_key_provider
    assert provider.get_key() is None
    key = provider.provision_key()
    assert key is not None
    assert key == provider.get_key()
    assert provider.destroy_key() is True
    assert provider.get_key() is None

    # The fixture exposes counters/state but never persists key material.
    observable = cast(Any, provider)
    assert observable.provision_calls == 1
    assert observable.get_calls == 3
    assert observable.destroy_calls == 1
    assert observable.persisted is False


def test_fake_atomic_writer_is_protocol_conformant_and_does_not_write_disk(
    fake_atomic_writer: AtomicWriter,
    data_root: Path,
) -> None:
    assert isinstance(fake_atomic_writer, AtomicWriter)
    destination = data_root / "profile.enc"
    payload = b"synthetic-ciphertext"
    fake_atomic_writer.write_atomic(destination, payload)

    assert not destination.exists()
    writes = cast(Any, fake_atomic_writer).writes
    assert writes == [(destination, payload)]


def test_fake_profile_store_is_protocol_conformant_and_isolated(
    fake_profile_store: ProfileStore,
) -> None:
    assert isinstance(fake_profile_store, ProfileStore)
    store = fake_profile_store
    assert store.read() is None

    # ``model_construct`` is used only to exercise the storage seam; no profile
    # behavior or validation belongs in this fixture task.
    snapshot = ProfileSnapshot.model_construct(profile_id="synthetic", profile_version=1)
    store.write(snapshot)
    assert store.read() is snapshot
    store.delete()
    assert store.read() is None
    observable = cast(Any, store)
    assert observable.write_calls == 1
    assert observable.read_calls == 3
    assert observable.delete_calls == 1


def test_fixture_module_never_initializes_real_keyring(
    fake_key_provider: KeyProvider,
    data_root: Path,
) -> None:
    """The fake explicitly advertises its offline nature and leaves no key files."""

    assert cast(Any, fake_key_provider).backend == "memory"
    assert list(data_root.rglob("*")) == []
