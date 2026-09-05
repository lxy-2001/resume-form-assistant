# F002 Research Decisions

## Decision 1: Reuse the existing v0.1 import contract

- **Decision**: Implement `DocumentRef`, `ProfileImportPreviewRequest`, `ProfileImportCandidate`, `ImportDecision`, and `ProfileImportConfirm*` as the cross-module boundary.
- **Rationale**: The contract already expresses source, confidence, evidence, consent, OCR usage, and confirmation. A second format would split meanings between the extension and local service.
- **Alternatives considered**: Add a private parser response format; rejected because it would violate the shared-contract rule.

## Decision 2: Keep parsing, candidate generation, and persistence separate

- **Decision**: Parser returns located text segments; candidate generation returns review candidates; confirmation reuses F001 persistence.
- **Rationale**: This prevents unconfirmed data from entering the profile store and makes PDF/DOCX/OCR replaceable behind focused seams.
- **Alternatives considered**: Let the parser write directly to ProfileService; rejected because it would bypass review and conflict protection.

## Decision 3: Local-first OCR and model use

- **Decision**: OCR runs locally when needed. Remote model use remains disabled unless the request contains explicit consent and the response reports the outbound status.
- **Rationale**: This follows the Constitution and product baseline and keeps ordinary parsing usable without a provider.
- **Alternatives considered**: Always upload documents for semantic extraction; rejected on privacy and availability grounds.

## Decision 4: Reject `.doc` in F002 despite a compatibility media type in v0.1

- **Decision**: The implementation accepts PDF and DOCX only; `.doc` is rejected with a stable unsupported-format result.
- **Rationale**: This is the user-approved F002 scope. The existing `application/msword` enum is compatibility surface, not a promise that F002 implements it.
- **Alternatives considered**: Implement `.doc` immediately; rejected as scope expansion.

## Decision 5: Short-lived import task state

- **Decision**: Keep raw segments, OCR output, and unconfirmed candidates only for the import task lifetime; do not add a permanent document store in F002.
- **Rationale**: It reduces privacy exposure and avoids introducing a database or long-term memory before the feature needs one.
- **Alternatives considered**: Persist every uploaded document; rejected because the product baseline does not require it.

## Environment verification (2026-09-05)

- The bundled Python runtime provides `pypdf`, `pdfplumber`, `python-docx`, `Pillow`, `pdf2image`, `pypdfium2`, and Poppler command-line tools.
- The bundled runtime does not provide Tesseract or another OCR executable. A project-local `.venv` was created for verification with the parser, test, lint, and type-check dependencies; extension dependencies were installed locally as ignored workspace artifacts.
- **Impact**: PDF/DOCX extraction and the OCR adapter seam are verified. The Tesseract adapter reports `OCR_UNAVAILABLE` when the executable is absent; no implementation claims OCR success without a local backend. Installing or selecting a concrete OCR engine remains an environment setup concern and is outside the F002 code contract.

## Contract transport note

The existing shared import schema describes metadata, candidates, and confirmation but does not
carry file bytes. F002 therefore adds a bounded `content_base64` request member for the local
extension-to-agent preview call, while keeping remote model consent false by default. The
confirmation request now carries `profile_id` and `expected_profile_version` so a review cannot
silently write against a changed profile.
