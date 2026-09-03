"""Typed storage errors sharing lifecycle response semantics."""

from __future__ import annotations

from resume_agent.profile.errors import LifecycleError


class StorageError(LifecycleError):
    """Base class for local storage failures."""


class StorageUnavailableError(StorageError):
    code = "STORAGE_UNAVAILABLE"


class StorageCorruptOrUnrecoverableError(StorageError):
    code = "STORAGE_CORRUPT_OR_UNRECOVERABLE"
