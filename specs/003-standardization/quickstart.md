# F003 Quickstart

## Local preview

1. Prepare a redacted F002 import task from a PDF/DOCX fixture.
2. Read the current F001 profile and capture `profile_id` and `profile_version`.
3. Request a normalization preview for the F002 task with remote consent disabled.
4. Verify every candidate includes normalized value, source, confidence, status and issues.
5. Confirm one ordinary field, modify one date, reject one conflict, and leave one candidate unconfirmed.
6. Read F001 again and verify only the explicitly confirmed result changed.
7. Reuse the same request id and verify the response is replayed without duplicate writes.
8. Change the profile between preview and confirm and verify the confirm request is rejected as stale.

## Required checks

- Contract schema and examples validate.
- Local-agent unit and API tests cover normalization, conflicts, records, cancellation, TTL and stale versions.
- Extension tests cover evidence, confidence, issue, correction and cancel states.
- Ruff, mypy, TypeScript, ESLint and Vite build pass.
- No fixture contains real personal data, API keys or exported profile files.

## Verification record (2026-09-05)

- Local-agent: 272 tests passed; Ruff check/format and mypy passed.
- Shared contracts: 58 tests passed and schema JSON parsed successfully.
- Extension: 36 tests passed; TypeScript, ESLint and Vite build passed.
- Untracked temporary files in the workspace were left untouched.
