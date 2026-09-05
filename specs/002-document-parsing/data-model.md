# F002 Data Model

## DocumentRef

- `document_id`: opaque task/document identifier.
- `filename`: display name only; never used as an unrestricted filesystem path.
- `media_type`: supported input type (`application/pdf` or DOCX media type for F002).
- `size_bytes`: validated non-negative size within configured limit.
- `sha256`: content identity used for traceability and duplicate task checks.

## ParsedSegment

- `segment_id`: task-local identifier.
- `document_id`: owning document.
- `text`: extracted or OCR text kept only for the task lifetime.
- `location`: page/region for PDF or paragraph/table location for DOCX.
- `evidence`: short displayable excerpt.
- `extraction_method`: text, OCR, or table/paragraph extraction.
- `warnings`: local parsing warnings.

## ProfileImportCandidate

Uses the shared contract fields: candidate ID, standard field ID, label, field type, value, `Source`, confidence, evidence, `requires_confirmation=true`, and warnings. A candidate is not a persisted `FieldValue`.

## ImportTask

- `task_id`, `document_id`, request ID;
- lifecycle: validating → extracting → ocr (optional) → candidates_ready → awaiting_user_review → confirming → completed/failed/cancelled/expired;
- captured profile version at preview time;
- candidate list and warnings;
- consent and outbound model metadata.

Task state is short-lived and must not be exposed as a permanent profile snapshot.

## Confirmation decision

`accept`, `modify`, or `reject`. Accept/modify must pass F001 validation and version checks before persistence. Reject, cancel, expired, or stale decisions cause no profile mutation.

## Invariants

1. Preview never mutates the profile snapshot or profile version.
2. Every candidate requires confirmation.
3. Every candidate has a source and confidence.
4. Sensitive candidates cannot bypass confirmation.
5. A stale profile version cannot be written.
6. Raw document and intermediate text are not returned in ordinary error responses or logs.
