"""Dependency-injection protocols for local profile persistence.

Implementations are provided by later storage tasks; these interfaces deliberately
perform no filesystem or cryptographic I/O.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from resume_agent.profile.models import ProfileSnapshot


@runtime_checkable
class ProfileStore(Protocol):
    """Read, atomically replace, or delete the complete confirmed snapshot."""

    def read(self) -> ProfileSnapshot | None:
        """Return the current snapshot, or ``None`` when no profile exists."""

    def write(self, snapshot: ProfileSnapshot) -> None:
        """Persist a complete confirmed snapshot atomically."""

    def delete(self) -> None:
        """Remove the encrypted snapshot; be idempotent when already absent."""


@runtime_checkable
class AtomicWriter(Protocol):
    """Write bytes through a temp-file/fsync/replace implementation seam."""

    def write_atomic(self, destination: Path, payload: bytes) -> None:
        """Atomically replace ``destination`` with ``payload``; never writes here."""
