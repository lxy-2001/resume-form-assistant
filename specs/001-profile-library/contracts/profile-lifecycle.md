# F001 Contract Mapping: Profile Lifecycle

**Status**: Design proposal
**Authority**: packages/contracts/v0.1/contracts.schema.json remains the only normative schema.

This document maps F001 domain operations to the shared contract and identifies the small
upstream additions required before implementation. It is not a second schema and must not
be used to invent fields absent from the shared contract.

## Operations

| Logical operation | Caller → owner | Request | Response | F001 use |
| --- | --- | --- | --- | --- |
| profile.read | Options Page → local Agent | ProfileReadRequest | ProfileReadResponse | Load the current profile and empty state |
| profile.upsert | Options Page → local Agent | ProfileUpsertRequest | ProfileUpsertResponse | Create or edit confirmed values |
| profile.delete | Options Page → local Agent | ProfileDeleteRequest | ProfileDeleteResponse | Delete selected values, records or all data |
| profile.export | Options Page → local Agent | ProfileExportRequest | ProfileExportResponse | Export a user-selected local copy |

The current v0.1 contract already defines profile.upsert, including user confirmation and
field deletion IDs. It does not yet define the read, export and complete-delete messages.
Those definitions must be added to the upstream contracts PR before F001 runtime integration.

## Common Request Rules

- Every request carries schema_version 0.1, request_id and task_id.
- Mutating requests carry user_confirmed=true and are rejected if confirmation is absent.
- Requests identify a profile and an explicit scope or record selection; an omitted selection
  cannot mean “all data” unless the operation explicitly says so.
- The service validates field type, sensitivity, scope, custom-field collisions and version
  preconditions before changing storage.
- A repeated request with the same request_id is idempotent and must not duplicate records.

## Proposed Response Rules

### ProfileReadResponse

Returns the confirmed profile snapshot, field definitions needed by the page, repeatable
records, schema version and an explicit empty flag. It must not contain the encrypted storage
envelope, key material or internal stack traces.

### ProfileUpsertResponse

Reuses the existing response shape: operation result, written IDs, deleted IDs, warnings and
task state. It should include the resulting profile version in the upstream amendment so the
page can detect stale edits.

### ProfileDeleteResponse

Returns deleted field/record IDs, whether the requested selection was complete, warnings and
the resulting profile version. A cancelled confirmation produces no deletion and a structured
cancelled result rather than success. A full-profile deletion reports partial-failure if the
encrypted snapshot and its keyring reference cannot both be handled successfully.

### ProfileExportResponse

Returns export ID, selected scope summary, local destination status, resulting profile version
and warnings. It never returns file contents or a remote upload URL. The export format is a
versioned structured JSON document and is chosen only after the user confirms the scope.

## Error Semantics

Use the shared ErrorResponse categories and stable error codes for:

- invalid_field_value;
- custom_field_conflict;
- confirmation_required;
- stale_profile_version;
- storage_unavailable;
- storage_corrupt_or_unrecoverable;
- export_cancelled or export_failed;
- deletion_failed.

Error details must be actionable but must not echo sensitive values, complete export content,
keys or local absolute paths.

## Security Invariants

1. The contract contains no submit, next-step, browser, model or arbitrary-script operation.
2. Sensitive fields require confirmation; a response cannot downgrade sensitivity.
3. Existing values are never overwritten without an explicit user decision represented in the
   request.
4. Export is local and user initiated; the response cannot imply automatic upload.
5. The Options Page talks to the local Agent through this contract and never calls a model
   provider directly.

## Upstream Amendment Checklist

- [ ] Add ProfileReadRequest/ProfileReadResponse to the master JSON Schema and examples.
- [ ] Add ProfileDeleteRequest/ProfileDeleteResponse with explicit selection and confirmation.
- [ ] Add ProfileExportRequest/ProfileExportResponse with local-only destination semantics.
- [ ] Add contract tests for version, confirmation, stale-version and sensitive-field rules.
- [ ] Update the operation table and changelog in the contracts PR.

Until this checklist is satisfied, F001 may implement domain and storage tests but must not
ship an ad-hoc cross-module message format.
