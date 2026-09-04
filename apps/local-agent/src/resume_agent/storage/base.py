"""Dependency-injection protocols for local profile persistence."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from resume_agent.profile.models import ProfileSnapshot


@runtime_checkable
class ProfileStore(Protocol):
    """Read/replace/delete snapshot; implementations may raise StorageError and must not swallow errors."""

    def read(self) -> ProfileSnapshot | None: ...
    def write(self, snapshot: ProfileSnapshot) -> None: ...
    def delete(self) -> None: ...


@runtime_checkable
class ProfileDataDeletionStore(Protocol):
    """Optional explicit seam for deleting a snapshot and its key material.

    Implementations that own encryption metadata must expose this operation so
    the profile service never has to inspect private attributes such as a
    ``key_provider``. The method is idempotent and either completes all cleanup
    or raises a typed cleanup error.
    """

    def delete_profile_data(self) -> None: ...


@runtime_checkable
class AtomicWriter(Protocol):
    """Atomic bytes writer seam; implementations may raise StorageError."""

    def write_atomic(self, destination: Path, payload: bytes) -> None: ...
