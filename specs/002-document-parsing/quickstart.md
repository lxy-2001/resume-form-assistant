# F002 Quickstart Validation

## Preconditions

- Use only synthetic PDF, DOCX and image-PDF fixtures.
- Start the local service with its existing F001 development setup.
- Keep remote model consent disabled for the default scenarios.

## Scenario A: text extraction

1. Select a synthetic text PDF.
2. Request `profile.import.preview` with `ocr_mode=auto` and remote consent disabled.
3. Confirm candidates contain source document ID, location, evidence, confidence and `requires_confirmation=true`.
4. Read the profile and confirm its version and fields are unchanged.
5. Repeat with a DOCX containing paragraphs and a table.

## Scenario B: image PDF OCR

1. Select a synthetic image-only PDF.
2. Request preview with `ocr_mode=auto`.
3. Confirm the result reports `ocr_used=true` and candidates retain page/region evidence.
4. Repeat with `ocr_mode=never` and confirm a clear no-text result with no profile mutation.

## Scenario C: review and write

1. Preview a document containing an ordinary field, a sensitive field and a conflicting existing value.
2. Accept one candidate, modify one, and reject one.
3. Confirm the service revalidates values and writes only accepted/modified candidates.
4. Change the profile after preview, then confirm the old task is rejected as stale.

## Scenario D: failures and privacy

1. Try `.doc`, corrupt, encrypted, oversized and empty fixtures.
2. Confirm stable actionable errors and unchanged profile state.
3. Run preview with no remote consent and assert zero outbound calls.
4. Assert logs and errors do not contain document text, field values, secrets or full local paths.
5. Cancel a task and confirm its later confirmation cannot mutate the profile.

## Expected checks

- Contract validation for all import request/response examples.
- Local-agent unit and integration tests for parsers, task state, candidate review and profile integration.
- Privacy and outbound-request tests.
- Extension tests for file selection, candidate review, conflict display and cancellation.
