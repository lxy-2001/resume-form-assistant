# F001 Contract Mapping: Profile Lifecycle

**Status**: Done
**Authority**: `packages/contracts/v0.1/contracts.schema.json` remains the only normative schema.
**Upstream baseline**: shared-contracts PR #1, merged into `main` as `23b9d2b`.
**Implementation review**: F001 PR #2 and corrective PR #3 are merged; corrective merge commit is `c151e0a`.

This document maps F001 domain operations to the shared contract. It is an implementation guide,
not a second schema: fields, enum values and validation rules must be read from
`packages/contracts/`.

## Operations

| Logical operation | Caller → owner | Request | Response | F001 use |
| --- | --- | --- | --- | --- |
| `profile.read` | Options Page → local Agent | `ProfileReadRequest` | `ProfileReadResponse` | Load the current profile and explicit empty state |
| `profile.upsert` | Options Page → local Agent | `ProfileUpsertRequest` | `ProfileUpsertResponse` | Create or edit confirmed values |
| `profile.delete` | Options Page → local Agent | `ProfileDeleteRequest` | `ProfileDeleteResponse` | Delete selected values, records, custom definitions or all data |
| `profile.export` | Options Page → local Agent | `ProfileExportRequest` | `ProfileExportResponse` | Export a user-selected local JSON copy |

## Common Request Rules

- Every request carries `schema_version` `0.1`, `request_id` and `task_id`.
- `profile.read` is read-only and does not carry a confirmation flag or write payload.
- `profile.upsert`, `profile.delete` and `profile.export` carry `profile_id`,
  `expected_profile_version` and `user_confirmed=true`; a missing, false or stale value is rejected
  before storage changes.
- Delete and export requests must contain an explicit `selection`. `delete_all` and
  `all_profile_data` are explicit alternatives and cannot be mixed with partial selectors.
- Stored `ProfileField` values are confirmed and include `source` and `updated_at`. A
  `website` or `application` scoped value includes `scope_context`; a `global` value does not.
- `request_id` is the idempotency key for a retried local operation; a successful retry must not
  duplicate records or apply a mutation twice.

## Response Rules

### `ProfileReadResponse`

Returns a confirmed `ProfileSnapshot`, field definitions needed by the page, repeatable records,
the profile version and warnings. An empty profile is represented by `is_empty=true` with empty
`fields` and `records`; it is not an error or an implicit default value. The response never
contains the encrypted storage envelope, key material or internal stack traces.

### `ProfileUpsertResponse`

Returns the profile identity, the resulting `profile_version`, written IDs, deleted IDs and
warnings. A successful mutation advances the version once. Reads and exports do not advance it.

### `ProfileDeleteResponse`

Returns deleted field/record/custom-definition IDs, the resulting profile version,
`all_data_deleted`, warnings and `cleanup_pending`. A completed response has no pending cleanup.
A partial response must list pending cleanup and include at least one warning; it must not claim
that all data was deleted. Full-profile deletion handles the encrypted snapshot and key reference
according to the storage recovery rules.

The confirmation UI cancels before sending a delete request, so no mutation is made and no
success response is fabricated. The current wire contract has no delete-cancelled success state.

### `ProfileExportResponse`

Returns an `export_id`, the profile version read, selected IDs/scopes, local destination display
name, byte count and warnings. Success is represented by `task_state=completed` and
`status=written`. The request format is JSON and the destination is a confirmed `local_file`;
URLs and network-share paths are rejected. The response never carries exported contents, secret
keys or an upload URL.

If the user cancels before sending the request, no file or profile mutation occurs. If a local
file picker cancellation is reported after a request was created, use `ErrorResponse` with
`failed_operation=profile.export` and `EXPORT_CANCELLED`.

## Error Semantics

Lifecycle failures use the shared `ErrorResponse`; `failed_operation` identifies the operation
when applicable. The documented lifecycle codes are:

- `PROFILE_NOT_FOUND`;
- `CONFIRMATION_REQUIRED`;
- `STALE_PROFILE_VERSION`;
- `INVALID_PROFILE_SELECTION`;
- `INVALID_FIELD_VALUE`;
- `CUSTOM_FIELD_CONFLICT`;
- `STORAGE_UNAVAILABLE`;
- `STORAGE_CORRUPT_OR_UNRECOVERABLE`;
- `EXPORT_CANCELLED` or `EXPORT_FAILED`;
- `DELETE_FAILED` or `DELETE_PARTIAL`.

Error messages and `details` must be actionable but must not echo sensitive values, complete export
content, keys or complete local absolute paths.

## Security Invariants

1. The contract contains no submit, next-step, browser, model or arbitrary-script operation.
2. Sensitive fields require confirmation; a response cannot downgrade sensitivity or confirmation.
3. Existing values are never overwritten without an explicit user decision represented in the
   request.
4. Export is local and user initiated; the response cannot imply automatic upload.
5. The Options Page talks to the local Agent through this contract and never calls a model
   provider directly.

## Merge Checkpoint

- [x] `ProfileReadRequest` / `ProfileReadResponse` are present in the master Schema and examples.
- [x] `ProfileDeleteRequest` / `ProfileDeleteResponse` define explicit selection and confirmation.
- [x] `ProfileExportRequest` / `ProfileExportResponse` define local-only destination semantics.
- [x] Contract tests cover version, confirmation, stale-version, scope and sensitive-field rules.
- [x] Operation table, README and changelog were updated in shared-contracts PR #1.
- [x] The merged baseline and corrective implementation were verified on 2026-09-04: 58 contract/privacy tests passed.

F001 can now implement domain, storage, API and Options Page behavior without creating an ad-hoc
cross-module message format.
