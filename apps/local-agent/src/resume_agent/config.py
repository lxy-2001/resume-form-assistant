"""Pure, immutable configuration and user-data path helpers for F001.

The module performs no filesystem, network, or keyring I/O. Paths are normalized
lexically and every derived location is checked to remain under the configured
data root.
"""

from __future__ import annotations

import os
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from ipaddress import ip_address
from pathlib import Path
from typing import Any

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_REQUEST_LIMIT = 1_048_576
MAX_REQUEST_LIMIT = 16 * 1024 * 1024
DEFAULT_APP_NAME = "resume-agent"
DEFAULT_NAMESPACE = "resume_agent"
DEFAULT_ALLOWED_ORIGINS = ("http://127.0.0.1:5173", "http://localhost:5173")


def _normalize_root(value: str | Path) -> Path:
    root = Path(value).expanduser()
    if not root.is_absolute():
        raise ValueError("data_root must be an absolute path")
    return Path(os.path.normpath(str(root)))


def _validate_host(value: str) -> str:
    host = str(value).strip().lower()
    if host == "localhost":
        host = DEFAULT_HOST
    if not host:
        raise ValueError("host must be a loopback IP address")
    try:
        address = ip_address(host)
    except ValueError as exc:
        raise ValueError("host must be a loopback IP address") from exc
    if not address.is_loopback:
        raise ValueError("host must be loopback-only")
    return host


def _normalize_origins(value: object) -> tuple[str, ...]:
    if value is None:
        return DEFAULT_ALLOWED_ORIGINS
    values: tuple[object, ...]
    if isinstance(value, str):
        values = (value,)
    else:
        if not isinstance(value, Iterable):
            raise TypeError("allowed_origins must be an iterable of strings")
        try:
            values = tuple(value)
        except TypeError as exc:
            raise ValueError("allowed_origins must be an iterable of strings") from exc
    result: list[str] = []
    for origin in values:
        if not isinstance(origin, str):
            raise TypeError("allowed_origins must contain only strings")
        # Origins are security-sensitive identifiers. Do not silently trim a
        # value supplied by configuration; malformed whitespace must be rejected.
        if origin != origin.strip():
            raise ValueError("allowed_origins must contain exact origins")
        normalized = origin
        if not normalized or "*" in normalized or any(char.isspace() for char in normalized):
            raise ValueError("allowed_origins must contain exact origins")
        if len(normalized) > 256:
            raise ValueError("allowed origin is too long")
        if normalized not in result:
            result.append(normalized)
    return tuple(result)


def _has_parent_component(value: str | Path) -> bool:
    return ".." in Path(value).parts


def _lexical_child(root: Path, *parts: str | Path) -> Path:
    if any(_has_parent_component(part) for part in parts):
        raise ValueError("path escapes configured root (traversal is not allowed)")
    candidate = Path(os.path.normpath(str(root.joinpath(*parts))))
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("path escapes configured root") from exc
    return candidate


@dataclass(frozen=True, slots=True)
class AppConfig:
    """Validated local-agent settings with no construction side effects."""

    data_root: Path
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    request_limit: int = DEFAULT_REQUEST_LIMIT
    app_name: str = DEFAULT_APP_NAME
    namespace: str = DEFAULT_NAMESPACE
    allowed_origins: tuple[str, ...] = DEFAULT_ALLOWED_ORIGINS

    def __post_init__(self) -> None:
        object.__setattr__(self, "data_root", _normalize_root(self.data_root))
        object.__setattr__(self, "host", _validate_host(self.host))
        if (
            isinstance(self.port, bool)
            or not isinstance(self.port, int)
            or not 1 <= self.port <= 65_535
        ):
            raise ValueError("port must be an integer from 1 through 65535")
        if (
            isinstance(self.request_limit, bool)
            or not isinstance(self.request_limit, int)
            or not 1 <= self.request_limit <= MAX_REQUEST_LIMIT
        ):
            raise ValueError("request_limit is outside the safe bound")
        for field_name in ("app_name", "namespace"):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ValueError(f"{field_name} must not be empty")
            object.__setattr__(self, field_name, value)
        object.__setattr__(self, "allowed_origins", _normalize_origins(self.allowed_origins))

    @property
    def root(self) -> Path:
        return self.data_root

    @property
    def name(self) -> str:
        return self.app_name

    @property
    def request_limit_bytes(self) -> int:
        return self.request_limit

    @property
    def display(self) -> str:
        """Stable endpoint display value without a local filesystem path."""

        return f"http://{self.host}:{self.port}"

    @property
    def safe_display(self) -> str:
        return (
            f"AppConfig(name={self.app_name!r}, namespace={self.namespace!r}, "
            f"host={self.host!r}, port={self.port}, request_limit={self.request_limit})"
        )

    def to_dict(self, *, include_data_root: bool = False) -> dict[str, Any]:
        """Return stable safe settings; include the absolute path only explicitly."""

        result: dict[str, Any] = {
            "app_name": self.app_name,
            "namespace": self.namespace,
            "host": self.host,
            "port": self.port,
            "request_limit": self.request_limit,
            "allowed_origins": list(self.allowed_origins),
        }
        if include_data_root:
            result["data_root"] = str(self.data_root)
        return result

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any] | None = None, **overrides: Any) -> AppConfig:
        data = dict(values or {})
        data.update(overrides)
        if "root" in data and "data_root" not in data:
            data["data_root"] = data.pop("root")
        if "request_limit_bytes" in data and "request_limit" not in data:
            data["request_limit"] = data.pop("request_limit_bytes")
        if "name" in data and "app_name" not in data:
            data["app_name"] = data.pop("name")
        return cls(**data)

    def contains(self, path: str | Path) -> bool:
        candidate = Path(path)
        if _has_parent_component(candidate):
            return False
        if not candidate.is_absolute():
            candidate = self.data_root / candidate
        try:
            Path(os.path.normpath(str(candidate))).relative_to(self.data_root)
        except ValueError:
            return False
        return True

    def path(self, *parts: str | Path) -> Path:
        return _lexical_child(self.data_root, *parts)

    def user_data_path(self, *parts: str | Path) -> Path:
        return self.path(*parts)

    def profile_path(self, name: str = "profile.json") -> Path:
        return self.path(name)

    def answers_path(self, name: str = "answers.json") -> Path:
        return self.path(name)

    def artifacts_path(self, name: str | None = None) -> Path:
        return self.path("artifacts", *(() if name is None else (name,)))

    def temp_path(self, name: str = "request.tmp") -> Path:
        return self.path("tmp", name)

    def backup_path(self, name: str = "profile.json.bak") -> Path:
        return self.path("backup", name)

    def recovery_path(self, name: str = "recovery.json") -> Path:
        return self.path("recovery", name)

    def lock_path(self, name: str = "agent.lock") -> Path:
        return self.path("lock", name)


Config = AppConfig


def user_data_path(config: AppConfig, *parts: str | Path) -> Path:
    return config.user_data_path(*parts)


def profile_path(config: AppConfig, name: str = "profile.json") -> Path:
    return config.profile_path(name)


def answers_path(config: AppConfig, name: str = "answers.json") -> Path:
    return config.answers_path(name)


def artifacts_path(config: AppConfig, name: str | None = None) -> Path:
    return config.artifacts_path(name)


def temp_path(config: AppConfig, name: str = "request.tmp") -> Path:
    return config.temp_path(name)


def backup_path(config: AppConfig, name: str = "profile.json.bak") -> Path:
    return config.backup_path(name)


def recovery_path(config: AppConfig, name: str = "recovery.json") -> Path:
    return config.recovery_path(name)


def lock_path(config: AppConfig, name: str = "agent.lock") -> Path:
    return config.lock_path(name)
