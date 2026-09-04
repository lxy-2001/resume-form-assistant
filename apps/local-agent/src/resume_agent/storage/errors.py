"""Typed storage errors sharing lifecycle response semantics."""

from __future__ import annotations

from resume_agent.profile.errors import LifecycleError


class StorageError(LifecycleError):
    """Base class for local storage failures."""


class StorageUnavailableError(StorageError):
    code = "STORAGE_UNAVAILABLE"


class StorageCorruptOrUnrecoverableError(StorageError):
    code = "STORAGE_CORRUPT_OR_UNRECOVERABLE"


class StorageCleanupError(StorageUnavailableError):
    """A full-profile cleanup completed only for some storage components."""

    def __init__(self, message: str, *, pending: tuple[str, ...]) -> None:
        self.pending = tuple(dict.fromkeys(pending))
        super().__init__(message, details={"pending": list(self.pending)})
