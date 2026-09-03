"""Typed seam for OS-backed key material providers (no keyring access here)."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

KeyMaterial = bytes


@runtime_checkable
class KeyProvider(Protocol):
    """Retrieve, provision, and destroy opaque encryption key material.

    ``None`` represents an unavailable or untrusted backend; callers must not
    substitute plaintext or invent a fallback key.
    """

    def get_key(self) -> KeyMaterial | None:
        """Return trusted key bytes, or ``None`` when unavailable/untrusted."""

    def provision_key(self) -> KeyMaterial | None:
        """Provision and return key bytes, or ``None`` if provisioning failed."""

    def destroy_key(self) -> bool:
        """Destroy key material and report whether destruction was performed."""
