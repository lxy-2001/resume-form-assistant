"""Runnable local-agent service entrypoint."""

from __future__ import annotations

import os
from pathlib import Path

import uvicorn
from fastapi import FastAPI

from resume_agent.api.app import create_app
from resume_agent.config import AppConfig
from resume_agent.profile.service import DEFAULT_PROFILE_ID, ProfileService
from resume_agent.storage.encrypted_json import EncryptedJsonProfileStore
from resume_agent.storage.key_provider import KeyringKeyProvider


def _allowed_origins(config: AppConfig) -> tuple[str, ...]:
    """Read optional exact origins without ever enabling a wildcard."""

    raw = os.environ.get("RESUME_AGENT_ALLOWED_ORIGINS")
    if raw is None:
        return config.allowed_origins
    # Preserve the raw entries so AppConfig's exact-origin validation rejects
    # accidental whitespace instead of silently broadening configuration.
    return AppConfig.from_mapping(
        config.to_dict(include_data_root=True),
        allowed_origins=tuple(raw.split(",")),
    ).allowed_origins


def create_runtime_app(config: AppConfig | None = None) -> FastAPI:
    """Assemble the encrypted profile store, service and loopback API."""

    effective_config = config or AppConfig(Path.home() / ".resume-agent")
    key_provider = KeyringKeyProvider(effective_config.namespace, DEFAULT_PROFILE_ID)
    store = EncryptedJsonProfileStore(
        effective_config.profile_path("profile.enc.json"),
        key_provider,
    )
    service = ProfileService(store, profile_id=DEFAULT_PROFILE_ID)
    return create_app(
        effective_config,
        allowed_origins=_allowed_origins(effective_config),
        profile_service=service,
    )


_CONFIG = AppConfig(Path.home() / ".resume-agent")
app = create_runtime_app(_CONFIG)


def main() -> None:
    """Start the loopback-only HTTP service."""

    uvicorn.run(app, host=_CONFIG.host, port=_CONFIG.port, log_level="info")


if __name__ == "__main__":
    main()


__all__ = ["app", "create_runtime_app", "main"]
