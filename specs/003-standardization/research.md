# F003 Research Decisions

## Decision 1: Add a separate normalization task boundary

- **Decision**: Keep F002 import tasks as the source of parsed candidates and add a short-lived F003 normalization task with preview, decision and cancel operations.
- **Rationale**: F002 already guarantees document parsing and candidate evidence. A separate task prevents normalization or record reconstruction from writing through the F001 import path before review.
- **Alternatives considered**: Expand F002 candidate generation in place; rejected because it would mix parsing, semantic grouping and persistence and make failure boundaries hard to test.

## Decision 2: Rules first, bounded local orchestration

- **Decision**: Implement normalization as deterministic local rules plus an explicit adapter seam for future structured semantic assistance. The adapter is disabled by default and returns an unavailable result instead of calling a remote provider.
- **Rationale**: Dates, contact formats, whitespace, enums and common aliases are explainable and testable without a model. Unknown record classification must remain visible for manual correction.
- **Alternatives considered**: Always call a model for every candidate; rejected for privacy, availability and unnecessary nondeterminism.

## Decision 3: Reuse F001 write semantics

- **Decision**: Confirmed fields and records are converted into the existing `ProfileService.upsert` input, using the captured profile version, user confirmation and request replay cache.
- **Rationale**: F001 already provides atomic encrypted snapshot writes, validation, stable record IDs and optimistic version checks. F003 should not create another persistence path.
- **Alternatives considered**: Store normalized results in a new database or write directly to the encrypted file; rejected as unnecessary infrastructure and a security boundary violation.

## Decision 4: Candidate-level conflict and duplicate review

- **Decision**: Keep multiple source candidates and classify them as new, unchanged, possible duplicate or conflict. The user must choose the final value or record operation.
- **Rationale**: Confidence is evidence for review, not permission to overwrite existing data. Preserving source candidates also supports later correction and audit explanations.
- **Alternatives considered**: Pick the highest-confidence candidate automatically; rejected because it can silently lose conflicting personal data.

## Decision 5: Extend the shared contract before implementation

- **Decision**: Add normalization task, candidate, issue and decision schemas to `packages/contracts/v0.1` before adding local-agent or extension behavior.
- **Rationale**: The repository treats the shared schema as the only cross-module truth. Contract tests can then prevent the extension and service from inventing different meanings for records, conflicts or correction decisions.
- **Alternatives considered**: Use private Python/TypeScript shapes; rejected by the project constitution.
