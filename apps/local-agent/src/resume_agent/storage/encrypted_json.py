"""Encrypted JSON persistence for the local profile snapshot."""

from __future__ import annotations

import base64
import binascii
import json
import os
import tempfile
import threading
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from pydantic import ValidationError

from resume_agent.profile.models import ProfileSnapshot
from resume_agent.storage.base import AtomicWriter
from resume_agent.storage.errors import (
    StorageCorruptOrUnrecoverableError,
    StorageUnavailableError,
)
from resume_agent.storage.key_provider import KEY_LENGTH, KeyProvider

ENVELOPE_VERSION = "1"
ALGORITHM = "AES-256-GCM"
NONCE_LENGTH = 12
DEFAULT_AAD = b"resume-agent/profile/v1"


def _corrupt(
    message: str = "profile data is corrupt or unrecoverable",
) -> StorageCorruptOrUnrecoverableError:
    return StorageCorruptOrUnrecoverableError(message)


def _key_bytes(key: object) -> bytes:
    if not isinstance(key, bytes) or len(key) != KEY_LENGTH:
        raise _corrupt("encryption key is invalid")
    return key


def _aad_bytes(aad: object) -> bytes:
    if not isinstance(aad, bytes) or not aad:
        raise _corrupt("authenticated data is invalid")
    return aad


def _b64(value: object, name: str) -> bytes:
    if not isinstance(value, str) or not value:
        raise _corrupt(f"encrypted envelope {name} is malformed")
    try:
        return base64.b64decode(value.encode("ascii"), validate=True)
    except (UnicodeEncodeError, ValueError, binascii.Error) as exc:
        raise _corrupt(
            f"encrypted envelope {name} is malformed; profile data is corrupt or unrecoverable"
        ) from exc


def encode_envelope(
    snapshot: ProfileSnapshot,
    key: bytes,
    *,
    aad: bytes = DEFAULT_AAD,
) -> dict[str, str]:
    """Encode a validated snapshot in an authenticated AES-GCM envelope."""

    key_bytes = _key_bytes(key)
    aad_bytes = _aad_bytes(aad)
    if not isinstance(snapshot, ProfileSnapshot):
        raise _corrupt("profile snapshot is invalid")
    try:
        plaintext = snapshot.to_json().encode("utf-8")
        nonce = os.urandom(NONCE_LENGTH)
        ciphertext = AESGCM(key_bytes).encrypt(nonce, plaintext, aad_bytes)
    except (TypeError, ValueError, OSError) as exc:
        raise _corrupt("profile encryption failed") from exc
    return {
        "schema_version": ENVELOPE_VERSION,
        "algorithm": ALGORITHM,
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
    }


def decode_envelope(
    payload: Mapping[str, Any] | bytes | str,
    key: bytes,
    *,
    aad: bytes = DEFAULT_AAD,
) -> ProfileSnapshot:
    """Authenticate and decode an encrypted profile envelope."""

    key_bytes = _key_bytes(key)
    aad_bytes = _aad_bytes(aad)
    if isinstance(payload, Mapping):
        envelope: Mapping[str, Any] = payload
    elif isinstance(payload, bytes | str):
        try:
            raw = payload.decode("utf-8") if isinstance(payload, bytes) else payload
            parsed = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise _corrupt("encrypted envelope is malformed") from exc
        if not isinstance(parsed, Mapping):
            raise _corrupt("encrypted envelope is malformed")
        envelope = parsed
    else:
        raise _corrupt("encrypted envelope is malformed")

    if envelope.get("schema_version") != ENVELOPE_VERSION or envelope.get("algorithm") != ALGORITHM:
        raise _corrupt("encrypted envelope version or algorithm is unsupported")
    if set(envelope) != {"schema_version", "algorithm", "nonce", "ciphertext"}:
        raise _corrupt("encrypted envelope is malformed")
    nonce = _b64(envelope.get("nonce"), "nonce")
    ciphertext = _b64(envelope.get("ciphertext"), "ciphertext")
    if len(nonce) != NONCE_LENGTH or len(ciphertext) < 16:
        raise _corrupt("encrypted envelope is malformed")
    try:
        plaintext = AESGCM(key_bytes).decrypt(nonce, ciphertext, aad_bytes)
        decoded = json.loads(plaintext.decode("utf-8"))
        return ProfileSnapshot.model_validate(decoded)
    except (
        InvalidTag,
        UnicodeDecodeError,
        json.JSONDecodeError,
        ValidationError,
        TypeError,
        ValueError,
    ) as exc:
        raise _corrupt("profile authentication or decoding failed") from exc


class FilesystemAtomicWriter:
    """Write bytes using a same-directory temporary file and atomic replace."""

    def write_atomic(self, destination: Path, payload: bytes) -> None:
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=destination.parent,
                prefix=f".{destination.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temporary = Path(handle.name)
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, destination)
            temporary = None
            try:
                directory_fd = os.open(destination.parent, os.O_RDONLY)
            except OSError:
                directory_fd = None
            if directory_fd is not None:
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
        except OSError as exc:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass
            raise StorageCorruptOrUnrecoverableError("profile write failed") from exc


_LOCK_REGISTRY: dict[Path, threading.RLock] = {}
_LOCK_REGISTRY_GUARD = threading.Lock()


def _path_lock(path: Path) -> threading.RLock:
    resolved = path.absolute()
    with _LOCK_REGISTRY_GUARD:
        return _LOCK_REGISTRY.setdefault(resolved, threading.RLock())


class EncryptedJsonProfileStore:
    """ProfileStore implementation backed by an encrypted JSON file."""

    def __init__(
        self,
        path: Path,
        key_provider: KeyProvider,
        *,
        atomic_writer: AtomicWriter | None = None,
        aad: bytes = DEFAULT_AAD,
    ) -> None:
        self.path = Path(path)
        self.key_provider = key_provider
        self.atomic_writer = atomic_writer or FilesystemAtomicWriter()
        self.aad = _aad_bytes(aad)
        self._lock = _path_lock(self.path)

    def _key_for_read(self) -> bytes:
        try:
            key = self.key_provider.get_key()
        except StorageUnavailableError:
            raise
        except Exception as exc:
            raise StorageUnavailableError("key provider is unavailable") from exc
        if key is None:
            raise StorageUnavailableError("encryption key is unavailable")
        try:
            return _key_bytes(key)
        except StorageCorruptOrUnrecoverableError as exc:
            raise StorageUnavailableError("encryption key is unavailable") from exc

    def _key_for_write(self) -> bytes:
        try:
            key = self.key_provider.get_key()
            if key is None:
                key = self.key_provider.provision_key()
        except StorageUnavailableError:
            raise
        except Exception as exc:
            raise StorageUnavailableError("key provider is unavailable") from exc
        if key is None:
            raise StorageUnavailableError("encryption key is unavailable")
        try:
            return _key_bytes(key)
        except StorageCorruptOrUnrecoverableError as exc:
            raise StorageUnavailableError("encryption key is unavailable") from exc

    def read(self) -> ProfileSnapshot | None:
        with self._lock:
            if not self.path.exists():
                return None
            try:
                payload = self.path.read_bytes()
            except OSError as exc:
                raise StorageUnavailableError("profile file is unavailable") from exc
            if not payload:
                raise _corrupt("profile file is empty")
            return decode_envelope(payload, self._key_for_read(), aad=self.aad)

    def write(self, snapshot: ProfileSnapshot) -> None:
        if not isinstance(snapshot, ProfileSnapshot):
            raise _corrupt("profile snapshot is invalid")
        with self._lock:
            envelope = encode_envelope(snapshot, self._key_for_write(), aad=self.aad)
            payload = json.dumps(
                envelope, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
            try:
                self.atomic_writer.write_atomic(self.path, payload)
            except StorageCorruptOrUnrecoverableError:
                raise
            except OSError as exc:
                raise StorageCorruptOrUnrecoverableError("profile write failed") from exc

    def delete(self) -> None:
        with self._lock:
            try:
                self.path.unlink(missing_ok=True)
            except OSError as exc:
                raise StorageUnavailableError("profile file could not be deleted") from exc

    def delete_profile_data(self) -> None:
        """Remove the encrypted snapshot, then clear its key reference."""

        with self._lock:
            self.delete()
            try:
                self.key_provider.destroy_key()
            except StorageUnavailableError:
                raise
            except Exception as exc:
                raise StorageUnavailableError("encryption key could not be deleted") from exc


__all__ = [
    "ALGORITHM",
    "DEFAULT_AAD",
    "EncryptedJsonProfileStore",
    "FilesystemAtomicWriter",
    "decode_envelope",
    "encode_envelope",
]
