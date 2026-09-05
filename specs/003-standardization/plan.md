# F003 Implementation Plan: 资料标准化与人工纠正

## Technical Context

- **Repository**: Python local-agent, TypeScript/Vite extension, JSON Schema shared contracts.
- **Existing seams**: F002 `ImportService` owns short-lived import tasks and located candidates; F001 `ProfileService` owns validation, optimistic versions, encrypted persistence and repeatable records; `profile_routes.py` registers lifecycle routes.
- **New seams**: `normalization/` owns rule normalization and task lifecycle; normalization API routes expose preview, confirm and cancel; Options UI renders normalized evidence and decisions.
- **Persistence**: No new database or permanent document store. Normalization tasks remain in memory with a TTL and are invalidated after confirm/cancel/expiry.
- **Remote policy**: No Provider call in F003. The structured adapter reports unavailable when not explicitly implemented; all responses include `model_used=false` and `remote_data_sent=false`.

## Architecture and Data Flow

```text
F002 ImportService task
  → NormalizationService.preview(source_task_id, profile_id)
  → rules.py canonicalization and validation
  → records.py grouping, duplicate/conflict classification
  → NormalizationTask response through shared contract
  → Options ImportPanel review/correction
  → NormalizationService.confirm(decisions, expected_profile_version)
  → ProfileService.upsert(fields, records, user_confirmed=True)
```

The preview captures the current profile version and reads a snapshot only. Confirmation validates task state, request replay, profile identity and expected version before translating accepted decisions into F001 field/record writes. No route writes directly to encrypted storage.

## Contract Changes

1. Add `NormalizationStatus`, `NormalizationTarget`, `NormalizationIssue`, `NormalizedCandidate`, `RecordCandidate`, `NormalizationDecision`, `ProfileNormalizationPreviewRequest/Response`, `ProfileNormalizationConfirmRequest/Response`, and `ProfileNormalizationCancelRequest/Response` to `packages/contracts/v0.1/contracts.schema.json`.
2. Add redacted examples for preview, confirm, cancel, conflict, invalid value and unclassified record cases.
3. Update contract README/changelog and JSON-schema validation tests.
4. Keep F002 import contracts backward compatible; normalization is an additional operation family.

## Backend Components

### `apps/local-agent/src/resume_agent/normalization/rules.py`

- Normalize whitespace and safe punctuation without changing user-visible semantics.
- Normalize dates to the existing F001 date representation, common phone/email/URL forms and known education aliases.
- Return a structured conversion result with original value, normalized value, confidence, warnings and issues.
- Never invent missing values or infer a high-risk identity value from weak text.

### `apps/local-agent/src/resume_agent/normalization/records.py`

- Group related F002 segments by source order and nearby headings.
- Classify only clear education/work/internship/project patterns; otherwise return `unknown` with an issue.
- Build field-level candidates and compare organization/school plus date ranges against current records.
- Emit new/unchanged/possible_duplicate/conflict/unclassified status and a user-visible reason.

### `apps/local-agent/src/resume_agent/normalization/service.py`

- Manage task TTL, source-task existence, profile snapshot and lifecycle.
- Produce candidates without mutating F001.
- Validate decisions, re-run rules and F001 validation, and convert accepted field/record decisions to one atomic upsert.
- Support idempotent confirm and explicit cancellation; reject expired, cancelled, stale or already-completed tasks.

### `apps/local-agent/src/resume_agent/api/normalization_routes.py`

- Add `/v0/profile/normalize/preview`, `/confirm` and `/cancel`.
- Enforce exact operation keys, contract identifiers, loopback/origin middleware, bounded request bodies and redacted errors.
- Reuse the existing replay cache and lifecycle error mapping.
- Return task state, candidates, issues, model/remote flags and profile version without returning full private documents.

### Registration and tests

- Register a single `NormalizationService` beside `ImportService` in the existing profile route assembly.
- Add unit tests for rules, grouping, duplicate classification, service lifecycle and decision conversion.
- Add route/contract tests for preview isolation, confirm, cancel, stale version, replay, invalid decisions, TTL and privacy flags.

## Extension Components

### `apps/extension/src/options/profileClient.ts`

- Add typed preview/confirm/cancel methods and discriminated candidate/issue types.
- Preserve the existing F002 import methods for backward compatibility.

### `apps/extension/src/options/components/ImportPanel.tsx`

- Add a normalization review stage after F002 preview.
- Show original value, normalized value, source/evidence, confidence, issues, duplicate/conflict status and existing value.
- Provide keyboard-accessible accept, edit, merge, skip, reject and cancel actions; never auto-confirm.
- Make sensitive, long-text, record and conflict actions visibly require confirmation.

### Extension tests

- Add component/client tests for normalization states, correction payloads, cancellation and stale errors.
- Keep existing F002 preview tests passing.

## Test Strategy

1. Contract schema validation and example round trips.
2. Rule table tests for valid, invalid, ambiguous and sensitive values.
3. Record grouping tests for each record type, unknown type, duplicate and conflict.
4. Service tests proving preview isolation, atomic confirm, stale version rejection, replay and task cleanup.
5. API tests proving bounded/local origin/error behavior and no remote calls.
6. Extension tests proving evidence/issue visibility and no implicit confirmation.
7. Full local-agent pytest, Ruff, mypy; extension test, TypeScript, ESLint and Vite build.

## Delivery Phases

- **Phase 1 — Contract and test seams**: shared schemas, examples, types and failing acceptance tests.
- **Phase 2 — Rule normalization**: value canonicalization, validation and issue model.
- **Phase 3 — Record grouping and merge preview**: repeatable records, duplicate/conflict classification and service preview.
- **Phase 4 — Confirm/cancel API and F001 integration**: atomic writes, versions, replay and cleanup.
- **Phase 5 — Options review UI**: evidence, confidence, corrections and explicit decisions.
- **Phase 6 — Converge and quality gates**: focused fixes, full checks, docs and PR review.

## Risks and Mitigations

- **Ambiguous record semantics**: keep `unknown` and require manual type selection; do not guess.
- **Overwriting current data**: compare captured version and classify conflicts; all writes go through F001.
- **Privacy leakage in evidence**: cap evidence length, redact error/log output and keep task memory-only.
- **Contract drift**: update schema, examples and tests in Phase 1 before service or UI changes.
