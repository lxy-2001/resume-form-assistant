"""Shared pytest configuration for deterministic local-agent tests.

The package source path is configured by ``pyproject.toml``.  Keep this module
free of profile data and service fixtures so feature-specific tests can add
their own synthetic fixtures without sharing user state.
"""

from __future__ import annotations


def pytest_configure(config: object) -> None:
    """Reserve a neutral marker namespace for local-agent tests."""

    # Deliberately no runtime setup: tests must remain offline and isolated.
    del config
