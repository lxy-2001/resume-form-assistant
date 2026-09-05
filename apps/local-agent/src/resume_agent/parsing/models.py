"""Transport-neutral parser output models."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ParsedSegment:
    text: str
    location: str
    evidence: str | None = None
    extraction_method: str = "text"
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("parsed segment text must not be blank")
        if not self.location.strip():
            raise ValueError("parsed segment location must not be blank")
        if self.evidence is None:
            object.__setattr__(self, "evidence", self.text[:240])
