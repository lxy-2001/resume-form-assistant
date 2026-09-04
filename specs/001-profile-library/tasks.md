---

description: "Task list for F001 local profile library"
---

# Tasks: 本地简历资料库

**Input**: Design documents from specs/001-profile-library/

**Prerequisites**: spec.md, plan.md, research.md, data-model.md, contracts/profile-lifecycle.md

**Tests**: Included because the project Constitution and TDD workflow require tests before behavior changes.

**Organization**: Tasks are grouped by user story so each story can be implemented and demonstrated independently.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish runnable local-service and Options Page project surfaces without personal data.

- [x] T001 Verified that shared-contracts PR #1 includes the lifecycle amendment, is merged into `main` at `23b9d2b`, updated the F001 branch, and recorded the merge reference in specs/001-profile-library/contracts/profile-lifecycle.md.
- [x] T002 [P] Create the Python project manifest and development commands in apps/local-agent/pyproject.toml.
- [x] T003 [P] Create the Options Page package manifest, TypeScript/Vite configuration, entry document, and development commands in apps/extension/package.json, apps/extension/tsconfig.json, apps/extension/vite.config.ts, and apps/extension/index.html.
- [x] T004 [P] Add synthetic F001 fixtures and fixture-handling rules in tests/fixtures/f001/README.md and apps/local-agent/tests/fixtures/f001_profiles.py.
- [x] T005 [P] Add local-service and Options Page test configuration in apps/local-agent/tests/conftest.py and apps/extension/vitest.config.ts.

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Establish the shared contract, domain boundaries, privacy defaults, and test seams before user-story work.

**CRITICAL**: No user-story implementation is complete until this phase and its contract checkpoint pass.

- [x] T006 Verified the merged lifecycle schema, examples, operation table, and contract tests for `profile.read`, `profile.delete`, and `profile.export` in packages/contracts/v0.1/contracts.schema.json, packages/contracts/v0.1/examples/, and tests/contracts/; 58 contract and privacy tests pass.
- [x] T007 [P] Define Profile, field definitions, field values, repeatable records, scopes, and serialization boundaries in apps/local-agent/src/resume_agent/profile/models.py.
- [x] T008 [P] Define typed domain/storage errors and privacy-safe error details in apps/local-agent/src/resume_agent/profile/errors.py, apps/local-agent/src/resume_agent/storage/errors.py, and apps/local-agent/src/resume_agent/privacy/redaction.py.
- [x] T009 [P] Define ProfileStore, KeyProvider, and atomic-writer interfaces in apps/local-agent/src/resume_agent/storage/base.py and apps/local-agent/src/resume_agent/storage/key_provider.py.
- [x] T010 [P] Define application configuration, user-data paths, and loopback service defaults in apps/local-agent/src/resume_agent/config.py.
- [x] T011 Create the local API application shell and request-size/error middleware in apps/local-agent/src/resume_agent/api/app.py.
- [x] T012 [P] Add shared synthetic profile builders and fake keyring/temp-directory fixtures in apps/local-agent/tests/conftest.py.

**Checkpoint**: The contract amendment, project setup, domain seams, and safety test fixtures are ready.

## Phase 3: User Story 1 - 手动维护基本资料 (Priority: P1) MVP

**Goal**: A user can create, view, edit, validate, and persist a basic profile locally.

**Independent Test**: With no browser site, document parser, or model provider, save synthetic name, email, and education data, restart the service, read it back, edit one value, and verify invalid input leaves the previous snapshot unchanged.

### Tests for User Story 1 (write first and observe failure)

- [x] T013 [P] [US1] Add domain tests for create, read, edit, cancel semantics, empty state, and stable timestamps in apps/local-agent/tests/unit/test_profile_service.py.
- [x] T014 [P] [US1] Add field-type and format validation tests for text, email, date, number, boolean, enum, and multi-value inputs in apps/local-agent/tests/unit/test_profile_validation.py.
- [x] T015 [P] [US1] Add encrypted-store tests for initialization, round-trip encryption, wrong/untrusted key backends, tamper detection, failed-write preservation, and absence of synthetic plaintext in the main/temp/backup files in apps/local-agent/tests/unit/test_encrypted_json.py.
- [x] T016 [P] [US1] Add local API contract tests for profile.read and profile.upsert success, confirmation, stale version, and structured errors in apps/local-agent/tests/contract/test_profile_routes.py.
- [x] T017 [P] [US1] Add Options Page tests for loading, editing, validation messages, and cancelling unsaved changes in apps/extension/tests/options/profile-page.test.tsx.

### Implementation for User Story 1

- [x] T018 [US1] Implement deterministic field validation, standard-field catalog loading, and confirmation policy in apps/local-agent/src/resume_agent/profile/validation.py, apps/local-agent/src/resume_agent/profile/standard_fields.py, and apps/local-agent/src/resume_agent/profile/policy.py.
- [x] T019 [US1] Implement the profile service for confirmed upsert, read, empty state, version checks, and non-mutating cancellation in apps/local-agent/src/resume_agent/profile/service.py.
- [x] T020 [US1] Implement allowlisted OS-keyring key provisioning and fail-closed behavior for unavailable, null, or untrusted backends in apps/local-agent/src/resume_agent/storage/key_provider.py.
- [x] T021 [US1] Implement versioned AES-GCM envelope encoding, decoding, and authenticated-data checks in apps/local-agent/src/resume_agent/storage/encrypted_json.py.
- [x] T022 [US1] Implement atomic temp-file flush, fsync, replace, single-writer locking, and last-valid-snapshot preservation, including injected fsync/replace failure handling, in apps/local-agent/src/resume_agent/storage/encrypted_json.py.
- [x] T023 [US1] Implement profile.read and profile.upsert routes with shared-envelope validation and redacted errors in apps/local-agent/src/resume_agent/api/profile_routes.py.
- [x] T024 [US1] Implement the Options Page profile client, basic profile form, field editor, empty state, and accessible error display in apps/extension/src/options/profileClient.ts, apps/extension/src/options/ProfilePage.tsx, and apps/extension/src/options/main.tsx.
- [x] T025 [US1] Add privacy-safe operation logging and ensure no profile values or keys are emitted in apps/local-agent/src/resume_agent/privacy/redaction.py and apps/local-agent/src/resume_agent/api/app.py.

**Checkpoint**: US1 is independently usable and all US1 tests pass; commit the MVP before starting US2.

## Phase 4: User Story 2 - 管理重复经历和简单自定义字段 (Priority: P2)

**Goal**: A user can maintain independent education/work/project records and create only confirmed, typed custom fields.

**Independent Test**: Add two education records, one project record, and an enum custom field; edit and delete individual items; verify conflict, invalid-option, and cancellation behavior.

### Tests for User Story 2 (write first and observe failure)

- [x] T026 [P] [US2] Add repeatable-record isolation, ordering, and deletion tests in apps/local-agent/tests/unit/test_repeatable_records.py.
- [x] T027 [P] [US2] Add custom-field type, option, scope, sensitivity, confirmation, and reserved-ID collision tests in apps/local-agent/tests/unit/test_custom_fields.py.
- [x] T028 [P] [US2] Add API contract tests for custom definitions and repeatable-record mutations in apps/local-agent/tests/contract/test_profile_custom_fields.py.
- [x] T029 [P] [US2] Add Options Page tests for adding, editing, reordering, deleting records and cancelling custom-field creation in apps/extension/tests/options/custom-fields.test.tsx.

### Implementation for User Story 2

- [x] T030 [US2] Extend domain models and serialization for repeatable records and custom definitions in apps/local-agent/src/resume_agent/profile/models.py.
- [x] T031 [US2] Implement custom-field collision, option, scope, and sensitivity validation in apps/local-agent/src/resume_agent/profile/validation.py.
- [x] T032 [US2] Implement confirmed repeatable-record and custom-field operations with optimistic version checks in apps/local-agent/src/resume_agent/profile/service.py.
- [x] T033 [US2] Expose repeatable-record and custom-field operations through the shared profile routes in apps/local-agent/src/resume_agent/api/profile_routes.py.
- [x] T034 [US2] Add reusable record editor, custom-field editor, type-specific controls, and confirmation states in apps/extension/src/options/components/RecordEditor2.tsx and apps/extension/src/options/components/CustomFieldEditor.tsx.
- [x] T035 [US2] Connect the new editors to the profile client and display scope, sensitivity, source, and confirmation metadata in apps/extension/src/options/ProfilePage.tsx and apps/extension/src/options/profileClient.ts.

**Checkpoint**: US1 remains green and US2 can be demonstrated without document parsing, model calls, or browser pages.

## Phase 5: User Story 3 - 查看、导出和删除本地资料 (Priority: P2)

**Goal**: A user can inspect metadata, export a selected local copy, and delete selected data with explicit confirmation.

**Independent Test**: Use synthetic ordinary, sensitive, and custom data; inspect metadata; export a subset; cancel and confirm deletions; simulate key and file failures.

### Tests for User Story 3 (write first and observe failure)

- [x] T036 [P] [US3] Add export-scope, format, confirmation, cancellation, and no-upload tests in apps/local-agent/tests/unit/test_profile_export.py.
- [x] T037 [P] [US3] Add deletion, key-reference cleanup, empty-state, and idempotency tests in apps/local-agent/tests/unit/test_profile_delete.py.
- [x] T038 [P] [US3] Add corrupted-file, missing-key, invalid-tag, untrusted-backend, interrupted-write, fsync/replace failure, recovery-message, and plaintext-leak tests in apps/local-agent/tests/integration/test_storage_recovery.py.
- [x] T039 [P] [US3] Add API contract tests for profile.delete and profile.export errors, selected scopes, and stale versions in apps/local-agent/tests/contract/test_profile_lifecycle.py.
- [x] T040 [P] [US3] Add Options Page tests for metadata display, export scope confirmation, deletion confirmation, cancellation, and failure feedback in apps/extension/tests/options/profile-lifecycle.test.tsx.
- [x] T041 [P] [US3] Add outbound-request and log-redaction assertions for all F001 operations in apps/local-agent/tests/integration/test_privacy_boundary.py.

### Implementation for User Story 3

- [x] T042 [US3] Implement selected-scope export with versioned structured output, user-chosen destination, and no-upload behavior in apps/local-agent/src/resume_agent/profile/export_service.py.
- [x] T043 [US3] Implement confirmed field/record/profile deletion and idempotency in apps/local-agent/src/resume_agent/profile/service.py; destroy the key reference only after confirmed full-profile deletion and successful encrypted-file removal in apps/local-agent/src/resume_agent/storage/encrypted_json.py.
- [x] T044 [US3] Expose profile.delete and profile.export with structured errors and response metadata in apps/local-agent/src/resume_agent/api/profile_routes.py.
- [x] T045 [US3] Add metadata panels, export scope dialog, deletion confirmations, and recoverable error states in apps/extension/src/options/components/ProfileMetadata.tsx and apps/extension/src/options/components/ProfileLifecycleDialogs.tsx.
- [x] T046 [US3] Connect export and delete actions and refresh the profile snapshot after each confirmed mutation in apps/extension/src/options/ProfilePage.tsx and apps/extension/src/options/profileClient.ts.

**Checkpoint**: US1, US2, and US3 pass their independent tests; no personal data leaves the local process.

## Phase 6: Polish and Cross-Cutting Concerns

**Purpose**: Verify non-functional requirements and keep documentation, packaging, and privacy boundaries aligned.

- [x] T047 [P] Add performance fixtures for 500 field values and 100 repeatable records in apps/local-agent/tests/performance/test_profile_latency.py.
- [x] T048 [P] Add keyboard navigation, labels, focus order, and accessible error requirements tests in apps/extension/tests/options/accessibility.test.tsx.
- [x] T049 [P] Add dependency and secret scans plus a synthetic-data audit in tests/security/test_f001_privacy_audit.py.
- [x] T050 [P] Update apps/local-agent/README.md and apps/extension/README.md with local setup, key recovery limits, and data deletion/export guidance.
- [x] T051 Run the scenarios in specs/001-profile-library/quickstart.md and record results in the F001 pull request.
- [x] T052 Run Python tests, TypeScript tests, type checks, formatters, contract checks, and privacy audits; record exact results in specs/001-profile-library/quickstart.md.
- [x] T053 Update docs/product/roadmap.md at each verified milestone; leave the final Done transition until the corrective review is merged.

## Dependencies and Execution Order

### Phase Dependencies

- Phase 1 (Setup) has no feature dependency and can start immediately.
- Phase 2 (Foundational) depends on Phase 1; T006 is complete because the shared-contracts PR is merged and verified.
- Phase 3 (US1) depends on all Phase 2 tasks and is the MVP checkpoint.
- Phase 4 (US2) depends on the domain and storage foundation plus the US1 profile snapshot semantics.
- Phase 5 (US3) depends on the US1 snapshot and the lifecycle contract amendment; its storage-recovery tests may be prepared in parallel with US2.
- Phase 6 (Polish) depends on the desired user stories being green.

### User Story Dependencies

- US1 (P1): starts after Phase 2 and has no dependency on another user story.
- US2 (P2): reuses the profile service from US1 but is independently testable with synthetic records.
- US3 (P2): reuses the encrypted snapshot and metadata from US1; export and deletion are independently testable.

### Within Each User Story

- Write the story tests first and observe them fail before implementing the behavior.
- Keep model/validation changes ahead of service changes, and service changes ahead of routes and UI.
- Run the story checkpoint before moving to the next story.
- Every mutation must preserve confirmation, version, and redaction invariants.

## Parallel Opportunities

- T002-T005 can run in parallel because they touch separate setup files.
- T007-T010 and T012 can run in parallel after the contract checkpoint is planned.
- T013-T017 are independent test files and can be authored in parallel.
- T026-T029 and T036-T041 are independent test files within their stories.
- T047-T050 are independent polish files after the functional stories are complete.

## Parallel Example: US1

    Task T013: profile service acceptance tests
    Task T014: field validation tests
    Task T015: encrypted storage tests
    Task T016: API contract tests
    Task T017: Options Page interaction tests

After the tests expose failures, implement T018-T025 in dependency order; storage and
validation internals may proceed in parallel once their interfaces exist.

## Implementation Strategy

### MVP First

1. Complete setup and foundational contract checks.
2. Complete US1 tests and implementation.
3. Stop at the US1 checkpoint and demonstrate create, read, edit, persistence, and invalid-input preservation.
4. Commit the MVP as a separately reviewable node before beginning US2.

### Incremental Delivery

1. Add US2 for repeatable records and confirmed custom fields.
2. Add US3 for metadata, export, deletion, and recovery.
3. Run polish and cross-cutting privacy/performance checks.
4. Use Converge to append any uncovered work before opening the F001 PR.

## Notes

- Every task uses the required checkbox, sequential ID, optional parallel marker, story label where applicable, and concrete file path format.
- The lifecycle contract amendment was merged through shared-contracts PR #1 and remains maintained in packages/contracts; it is not duplicated under the F001 directory.
- The key provider must fail closed for unavailable or untrusted backends; never add a plaintext fallback.
- Real profiles, API keys, local data, and exported files remain outside Git.

## Phase 7: Convergence

本阶段由实现后的规格收敛检查追加，用于关闭审阅中发现的剩余差距；仍遵守按 Phase 集中提交。

- [x] T054 [US3] 让 profile.upsert/delete 的响应准确报告实际删除的字段、记录和自定义定义（包括记录因字段变空而被移除，以及完整删除时记录字段），并补充路由回归测试。 per FR-017/契约响应规则；路由回归覆盖间接字段删除和空记录移除。
- [x] T055 [US1][US2] 收紧多值元素的字符串、非空、规范化和去重校验；自定义字段名称按去空白、大小写和标准别名检查冲突，并补充服务测试。 per FR-005/FR-009/Edge Cases；服务测试覆盖规范化、重复和冲突。
- [x] T056 [US3] 使本地生命周期请求的成功和 partial 终态在同一进程内可安全重试，补充 partial 重试和请求标识回归测试，并记录进程重启后的版本保护边界。 per profile-lifecycle idempotency rule；路由测试覆盖重放，契约文档记录进程重启由版本号保护。
- [x] T057 [US1][US3] 让 loopback/CORS 边界在缺少客户端地址时 fail-closed，确认请求体校验错误不回显输入，并补充启动入口、允许来源和错误响应文档。 per Constitution III/FR-014/plan API boundary；启动、来源、错误响应及 malformed nested JSON 边界测试和 README 已更新。
- [x] T058 [US2] 支持已确认自定义字段定义的受控修改（保留稳定 ID、校验既有值兼容性、同步字段元数据），并在 Options Page 提供明确的编辑确认入口。 per FR-008；服务与 Options Page 测试覆盖稳定 ID、既有值兼容和元数据同步。
- [x] T059 [US1][US2] 让顶层字段和重复记录使用类型感知控件，布尔值保留未选择状态，枚举显示允许选项，多值/富文本可编辑，并补充 UI 回归测试。 per FR-005/FR-006；类型控件、空状态和元数据 UI 回归测试通过。
- [x] T060 [US2] 允许新增重复记录后按标准目录补充多个记录字段；取消尚未持久化的记录时只移除本地草稿，不向服务发送未知删除请求。 per FR-003/FR-004/US2 AC5；记录编辑器测试覆盖标准目录字段和草稿取消。
- [x] T061 [US3] 为首次读取和失败的保存、导出、删除操作提供可操作的重试或人工处理入口，并在元数据中显示字段类型与自定义标记。 per FR-018/US3 AC5；读取/保存/导出/删除失败路径均提供重试或人工处理反馈。
