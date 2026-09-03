"""Placeholder service entrypoint for the local agent."""

from fastapi import FastAPI

app = FastAPI(title="Resume Agent", version="0.1.0")


def main() -> None:
    """Minimal console entrypoint; service orchestration is reserved for T011."""
    print("Resume Agent placeholder; service startup is implemented in T011.")
