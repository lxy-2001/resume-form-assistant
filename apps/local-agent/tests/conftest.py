"""Shared pytest configuration for deterministic local-agent tests.

The fixtures in this module are deliberately opt-in and synthetic.  They use
pytest's per-test temporary directory and in-memory protocol fakes so feature
tests cannot accidentally touch a user's profile, OS keyring, or network.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from fixtures.f001_profiles import (
    build_empty_profile,
    build_invalid_candidates,
    build_profile,
    clone_profile,
)
from resume_agent.config import AppConfig
from resume_agent.profile.models import ProfileSnapshot
from resume_agent.storage.base import AtomicWriter, ProfileStore
from resume_agent.storage.key_provider import KeyMaterial, KeyProvider


def pytest_configure(config: object) -> None:
    """Reserve a neutral marker namespace for local-agent tests."""

    # Deliberately no runtime setup: tests must remain offline and isolated.
    del config


SYNTHETIC_KEY: KeyMaterial = bytes(range(32))


@dataclass
class FakeKeyProvider:
    """In-memory ``KeyProvider`` fake with observable lifecycle counters."""

    key_material: KeyMaterial = SYNTHETIC_KEY
    key: KeyMaterial | None = None
    get_calls: int = 0
    provision_calls: int = 0
    destroy_calls: int = 0
    backend: str = "memory"
    persisted: bool = False

    def get_key(self) -> KeyMaterial | None:
        self.get_calls += 1
        return self.key

    def provision_key(self) -> KeyMaterial | None:
        self.provision_calls += 1
        self.key = bytes(self.key_material)
        return self.key

    def destroy_key(self) -> bool:
        self.destroy_calls += 1
        existed = self.key is not None
        self.key = None
        return existed


@dataclass
class FakeAtomicWriter:
    """Observable atomic-writer seam that intentionally never writes to disk."""

    writes: list[tuple[Path, bytes]] = field(default_factory=list)

    def write_atomic(self, destination: Path, payload: bytes) -> None:
        self.writes.append((Path(destination), bytes(payload)))


@dataclass
class FakeProfileStore:
    """Small in-memory ``ProfileStore`` fake for service/recovery tests."""

    snapshot: ProfileSnapshot | None = None
    read_calls: int = 0
    write_calls: int = 0
    delete_calls: int = 0
    writes: list[ProfileSnapshot] = field(default_factory=list)

    def read(self) -> ProfileSnapshot | None:
        self.read_calls += 1
        return self.snapshot

    def write(self, snapshot: ProfileSnapshot) -> None:
        self.write_calls += 1
        self.snapshot = snapshot
        self.writes.append(snapshot)

    def delete(self) -> None:
        self.delete_calls += 1
        self.snapshot = None


@pytest.fixture
def data_root(tmp_path: Path) -> Path:
    """Return a fresh, isolated temporary data root for one test."""

    root = tmp_path / "agent-data"
    root.mkdir()
    return root


@pytest.fixture
def temp_data_root(data_root: Path) -> Path:
    """Backward-friendly alias for the isolated temporary data root."""

    return data_root


@pytest.fixture
def app_config(data_root: Path) -> AppConfig:
    """Build side-effect-free local-agent configuration for ``data_root``."""

    return AppConfig(data_root)


@pytest.fixture
def config(app_config: AppConfig) -> AppConfig:
    """Short alias for tests that refer to the application configuration."""

    return app_config


@pytest.fixture
def fake_key_provider() -> FakeKeyProvider:
    """Return a fresh deterministic in-memory key provider."""

    return FakeKeyProvider()


@pytest.fixture
def fake_atomic_writer() -> FakeAtomicWriter:
    """Return a fresh writer fake whose calls remain observable in memory."""

    return FakeAtomicWriter()


@pytest.fixture
def fake_profile_store() -> FakeProfileStore:
    """Return a fresh in-memory profile-store seam."""

    return FakeProfileStore()


@pytest.fixture
def synthetic_profile() -> dict[str, Any]:
    """Wrap the canonical synthetic profile builder with a fresh deep value."""

    return build_profile()


@pytest.fixture
def empty_synthetic_profile() -> dict[str, Any]:
    """Wrap the canonical empty-profile builder with a fresh value."""

    return build_empty_profile()


@pytest.fixture
def invalid_candidates() -> list[dict[str, Any]]:
    """Return fresh deterministic invalid candidates for validation tests."""

    return build_invalid_candidates()


@pytest.fixture
def profile_builder() -> Callable[..., dict[str, Any]]:
    """Expose the existing profile builder without changing its public API."""

    return build_profile


@pytest.fixture
def profile_cloner() -> Callable[[dict[str, Any] | None], dict[str, Any]]:
    """Expose an independent-copy helper for mutation/conflict tests."""

    return clone_profile


@pytest.fixture
def key_provider(fake_key_provider: FakeKeyProvider) -> KeyProvider:
    """Protocol-typed alias for the fake provider."""

    return fake_key_provider


@pytest.fixture
def atomic_writer(fake_atomic_writer: FakeAtomicWriter) -> AtomicWriter:
    """Protocol-typed alias for the fake writer."""

    return fake_atomic_writer


@pytest.fixture
def profile_store(fake_profile_store: FakeProfileStore) -> ProfileStore:
    """Protocol-typed alias for the fake profile store."""

    return fake_profile_store
