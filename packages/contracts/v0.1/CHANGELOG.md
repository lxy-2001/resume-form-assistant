# Shared Contracts v0.1 Changelog

## Unreleased

### Added

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

- `ProfileField` now represents a confirmed stored value and requires source and update metadata;
  website/application values require `scope_context`, while global values forbid it.
- `ProfileUpsertRequest` now requires `profile_id` and `expected_profile_version`;
  `ProfileUpsertResponse` returns the resulting `profile_version`.
- `ErrorResponse` can identify a failed profile lifecycle operation and then restricts its error
  code to the documented lifecycle set.

These changes are part of the not-yet-released v0.1 baseline in PR #1. Once v0.1 is released,
new required fields or changed semantics require an explicit contract-version migration.
