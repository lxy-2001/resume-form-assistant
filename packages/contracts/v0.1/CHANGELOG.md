# Shared Contracts v0.1 Changelog

## Unreleased

### Added

- Added the F002 document import preview/confirmation examples and fields for local content
  transport, candidate sensitivity, existing-value conflicts, and resulting profile versions.
- Added local import cancellation request/response contracts so cancelling a preview invalidates
  its short-lived task before any confirmation can write.

- Added precise `field_values` selectors for profile deletion and export so one scoped value can
  be selected when a field ID exists in multiple scopes.

- Added `profile.read` request/response contracts with a versioned `ProfileSnapshot` and an
  explicit empty state.
- Added confirmed, version-checked `profile.delete` contracts with field, record, custom-field
  definition, and full-profile selections.
- Added confirmed, version-checked `profile.export` contracts restricted to user-selected local
  JSON files (excluding URLs and network shares); responses never carry exported contents or
  upload URLs.
- Added reusable profile field-definition, repeatable-record, selection, local-destination, and
  lifecycle error-code definitions.
- Added lifecycle examples and contract tests for confirmation, selection, scope context,
  partial cleanup, and local-only export invariants.

### Changed

- `ProfileImportPreviewRequest` may carry bounded base64 document content for a local-only
  preview transport; `ProfileImportConfirmRequest` requires the target profile and expected
  profile version so confirmation remains optimistic-concurrency checked.

- `ProfileField` now represents a confirmed stored value and requires source and update metadata;
  website/application values require `scope_context`, while global values forbid it.
- `ProfileUpsertRequest` now requires `profile_id` and `expected_profile_version`;
  `ProfileUpsertResponse` returns the resulting `profile_version`.
- `ErrorResponse` can identify a failed profile lifecycle operation and then restricts its error
  code to the documented lifecycle set.

These changes are part of the not-yet-released v0.1 baseline in PR #1. Once v0.1 is released,
new required fields or changed semantics require an explicit contract-version migration.

- Added F003 normalization preview/confirmation/cancellation operations with source, confidence, issue, conflict and record-candidate fields.
