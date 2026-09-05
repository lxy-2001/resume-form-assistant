# F003 Tasks: 资料标准化与人工纠正

## Phase 1 — Setup

- [x] T001 [P] Add F003 feature metadata and update `.specify/feature.json` to `specs/003-standardization`
- [x] T002 [P] Record F003 research decisions and data model in `specs/003-standardization/research.md` and `specs/003-standardization/data-model.md`
- [x] T003 Update `docs/product/roadmap.md` to mark F003 as Specifying and document the approved scope and branch

## Phase 2 — Foundational contract and test seams

- [x] T004 [P] Add normalization operation and candidate schemas to `packages/contracts/v0.1/contracts.schema.json`
- [x] T005 [P] Add redacted normalization preview/confirm/cancel examples under `packages/contracts/v0.1/examples/`
- [x] T006 [P] Add contract validation tests for normalization candidates, issues, record decisions and consent flags in `tests/contracts/`
- [x] T007 Add normalization request/response types and operation names to `apps/local-agent/src/resume_agent/profile/models.py` or a focused normalization model module
- [x] T008 Add extension normalization types and client method signatures in `apps/extension/src/options/profileClient.ts`
- [x] T009 Add failing acceptance tests for preview isolation, explicit confirmation, stale versions and privacy flags in `apps/local-agent/tests/contract/test_normalization_routes.py`

## Phase 3 — User Story 1: 标准字段清理与归一化

**Goal**: Convert clear F002 field candidates into validated, traceable normalized candidates without mutating F001.

**Independent test**: Rule and service tests prove valid normalization, invalid values, duplicate source candidates and preview isolation.

- [x] T010 [P] [US1] Add rule normalization fixtures for whitespace, dates, phone, email, URL, numbers and education aliases in `apps/local-agent/tests/fixtures/normalization/`
- [x] T011 [P] [US1] Implement value normalization result and issue models in `apps/local-agent/src/resume_agent/normalization/models.py`
- [x] T012 [US1] Implement deterministic field normalization and F001 validation adapters in `apps/local-agent/src/resume_agent/normalization/rules.py`
- [x] T013 [US1] Add unit tests for accepted, rejected and ambiguous values in `apps/local-agent/tests/unit/test_normalization_rules.py`
- [x] T014 [US1] Implement field candidate projection with original value, normalized value, evidence, confidence and source in `apps/local-agent/src/resume_agent/normalization/fields.py`
- [x] T015 [US1] Add service tests proving multiple sources remain visible and preview does not change the profile in `apps/local-agent/tests/unit/test_normalization_service.py`

## Phase 4 — User Story 2: 重复经历归类与资料合并

**Goal**: Group clear education/work/internship/project segments and classify new, unchanged, duplicate and conflict outcomes for review.

**Independent test**: Record fixtures produce traceable record candidates and never persist an unconfirmed record.

- [x] T016 [P] [US2] Add redacted multi-record segment fixtures and expected classifications in `apps/local-agent/tests/fixtures/normalization/records/`
- [x] T017 [US2] Implement nearby-heading and source-order grouping in `apps/local-agent/src/resume_agent/normalization/records.py`
- [x] T018 [US2] Implement record type classification with explicit `unknown` fallback and issues in `apps/local-agent/src/resume_agent/normalization/records.py`
- [x] T019 [US2] Implement existing-record comparison for new, unchanged, possible duplicate and conflict statuses in `apps/local-agent/src/resume_agent/normalization/merge.py`
- [x] T020 [US2] Add unit tests for record grouping, unknown type, duplicate overlap and field conflicts in `apps/local-agent/tests/unit/test_normalization_records.py`
- [x] T021 [US2] Add normalization preview integration tests for field and record candidates in `apps/local-agent/tests/contract/test_normalization_preview.py`

## Phase 5 — User Story 3: 人工纠正与确认写入

**Goal**: Let users correct and explicitly confirm normalized fields and records through atomic F001 writes.

**Independent test**: Confirm tests prove accepted changes persist, rejected/uncertain changes do not, and stale/replayed requests are safe.

- [x] T022 [US3] Implement task lifecycle, TTL and source-task lookup in `apps/local-agent/src/resume_agent/normalization/service.py`
- [x] T023 [US3] Add decision validation and re-normalization tests for accept, modify, merge, skip and reject in `apps/local-agent/tests/unit/test_normalization_decisions.py`
- [x] T024 [US3] Implement atomic decision conversion to `ProfileService.upsert` fields and records with explicit confirmation in `apps/local-agent/src/resume_agent/normalization/service.py`
- [x] T025 [US3] Implement normalization preview, confirm and cancel routes in `apps/local-agent/src/resume_agent/api/normalization_routes.py`
- [x] T026 [US3] Register normalization routes and services through the existing app/profile route assembly in `apps/local-agent/src/resume_agent/api/profile_routes.py` and `apps/local-agent/src/resume_agent/api/app.py`
- [x] T027 [US3] Add route tests for confirm persistence, stale version, invalid decision, cancellation, expiry and idempotent replay in `apps/local-agent/tests/contract/test_normalization_routes.py`

## Phase 6 — User Story 4: 失败处理与隐私边界

**Goal**: Make failures, unsupported semantics and privacy behavior explicit and fail closed.

**Independent test**: Failure tests prove no profile mutation, no remote call and redacted errors for every terminal failure.

- [x] T028 [P] [US4] Add stable normalization error codes and redacted details in `apps/local-agent/src/resume_agent/normalization/errors.py` and `apps/local-agent/src/resume_agent/privacy/redaction.py`
- [x] T029 [US4] Add tests for empty input, invalid values, unavailable semantic adapter, storage failure, task expiry and cleanup in `apps/local-agent/tests/unit/test_normalization_failures.py`
- [x] T030 [US4] Add API privacy tests proving `model_used=false`, `remote_data_sent=false`, no evidence leakage and exact loopback/origin enforcement in `apps/local-agent/tests/contract/test_normalization_privacy.py`

## Phase 7 — Options review and cross-cutting polish

- [x] T031 [US3] Implement normalization review state, evidence, confidence, issue and conflict rendering in `apps/extension/src/options/components/ImportPanel.tsx`
- [x] T032 [US3] Implement keyboard-accessible edit, merge, accept, skip, reject and cancel controls in `apps/extension/src/options/components/NormalizationReview.tsx`
- [x] T033 [US3] Add extension client/component tests for explicit decisions, correction payloads, cancellation and stale errors in `apps/extension/src/options/`
- [x] T034 [P] Update `apps/local-agent/README.md`, `apps/extension/README.md`, `packages/contracts/v0.1/README.md` and `CHANGELOG.md` with F003 behavior and privacy boundaries
- [x] T035 Run targeted and full verification: local-agent pytest, contract tests, Ruff, mypy, extension tests, TypeScript, ESLint and Vite build; record results in `specs/003-standardization/quickstart.md`
- [x] T036 Run `speckit-converge` and `speckit-analyze`, resolve all critical/high findings, and update this task list with any remaining bounded work

## Dependencies and Execution Order

```text
T001-T003 → T004-T009 →
  T010-T015 (US1) → T016-T021 (US2) → T022-T027 (US3) → T028-T030 (US4)
  → T031-T036 (UI, docs, verification)
```

- T004–T009 are foundational and must complete before service or UI behavior.
- T010–T015 can proceed in parallel within US1 after T009; T016–T021 depend on the candidate model from US1.
- T022–T027 depend on both field and record candidate models.
- T031–T033 depend on the stable contract and API response shape.
- T034–T036 happen after all user stories pass their independent tests.

## Parallel Opportunities

- T004/T005/T006/T008 can be developed in parallel after the data model is agreed.
- T010/T011 can proceed in parallel; T013 follows T012.
- T016 fixtures and T017 grouping can proceed in parallel; T020 follows T017–T019.
- T028 and T029 can proceed in parallel with the route hardening work.
- T034 documentation can proceed in parallel with T031 UI implementation.

## Implementation Strategy

1. Deliver a rules-only field normalization preview (US1) with no persistence.
2. Add record grouping and conflict classification (US2) while keeping unknowns manual.
3. Add explicit decision confirmation through the existing F001 atomic write path (US3).
4. Add review UI, privacy/failure hardening, documentation and full verification.

Total tasks: **36**.
