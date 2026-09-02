# Implementation Plan: 本地简历资料库

**Branch**: feat/F001-profile-library | **Date**: 2026-09-02 | **Spec**: spec.md

**Input**: Feature specification from specs/001-profile-library/spec.md

## Summary

本 Feature 实现一个单用户、本地优先的简历资料库：用户通过资料库页面手动维护标准字段、重复经历和简单自定义字段；本地服务负责确定性校验、确认策略、加密持久化、导出和删除；资料结构通过共享契约供后续 Feature 使用。F001 不调用模型、不解析文档、不读取或操作第三方网页。

首版采用后端无关的 ProfileStore 接口和加密 JSON 文件实现。资料序列化为单个版本化文档，使用 AES-GCM 保护，密钥由操作系统凭据存储托管；写入采用同目录临时文件、刷新并原子替换，确保中断时保留最近一次有效资料。该方案适合单用户和当前规模，同时为未来迁移到加密数据库保留接口边界。

## Technical Context

**Language/Version**: 本地服务 Python 3.11；资料库页面 TypeScript 5.x。跨模块消息使用 JSON Schema Draft 2020-12 v0.1。

**Primary Dependencies**: FastAPI、Pydantic、Uvicorn、cryptography、keyring、platformdirs；页面使用 React 与 Vite；测试使用 pytest、httpx、Vitest/Testing Library。只引入当前 Feature 必需的依赖。

**Storage**: 用户应用数据目录中的版本化加密 JSON 文件；随机数据加密密钥存放在操作系统凭据存储中。禁止明文降级、明文临时文件和把密钥写入资料文件。

**Testing**: pytest（领域、验证、存储和 API 契约测试）；httpx（本地 API 测试）；Vitest/Testing Library（资料页面交互测试）；网络拦截和脱敏审计测试覆盖隐私不变量。

**Target Platform**: Windows 11 + Chrome/Edge Manifest V3 为首个可运行目标；存储接口和路径抽象保留 macOS/Linux 后续支持。

**Project Type**: 浏览器扩展的 Options Page + 本地 loopback 服务；F001 只实现资料库页面和资料服务，不实现页面 Content Script、Side Panel 或浏览器动作。F004 负责后续扩展生命周期、Content Script、Side Panel 和最终通信接入；F001 的 Options Page 仅提供可复用的资料维护入口。

**Performance Goals**: 在不超过 500 个字段值和 100 条重复记录时，资料读取和单次保存的用户可感知等待时间 p95 不超过 1 秒。

**Constraints**: 单用户、本地运行；F001 的资料操作不产生个人资料出站请求；所有写入和删除都经过确认与校验；不能自动提交申请、导航网页或调用模型；共享契约 PR #1 合并后才能进入跨模块运行时实现。

**Scale/Scope**: 一台设备、一套主资料、最多 500 个字段值和 100 条重复记录；不做账户、云同步、多人协作或并发多用户服务。

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Result |
| --- | --- | --- |
| I. User-Controlled Safety and Reversibility | F001 不执行网页动作；敏感字段、自定义字段和删除有确认；失败不覆盖有效资料 | PASS |
| II. Deterministic-First, Bounded Agent | 只实现本地规则和结构化资料服务；不调用 Agent，不执行任意代码 | PASS |
| III. Local-First Privacy and Least Privilege | 加密静态存储、OS 凭据托管、零远程资料发送、日志脱敏 | PASS |
| IV. Contract- and Test-First | 复用 packages/contracts；先写验收测试；契约缺口在实现前显式解决 | PASS |
| V. Incremental and Traceable Feature Delivery | 独立 F001 分支，拥有完整 SDD 产物，节点提交并通过 PR | PASS |

No constitution violations require a complexity exception.

## Design Decisions and Dependencies

1. 资料库页面作为用户入口，Options Page 只负责展示表单、收集用户决定和显示结果；资料值由本地服务保存，页面不建立第二份长期资料副本。
2. 领域层提供 ProfileStore、FieldValidator、ConfirmationPolicy 和 ExportService 等窄接口；API、页面和存储实现通过接口组合，避免把 UI 或 HTTP 细节写进资料模型。
3. 首版使用加密 JSON 文件而不是 SQLCipher 或字段可查询数据库。当前数据量小、整文档加密可减少字段名和元数据泄露，且安装和测试成本低；当出现多份资料、复杂查询、导入历史或高并发需求时再评估加密数据库迁移。
4. 上游契约 PR #1 当前已有 profile.upsert 和删除字段语义，但缺少资料读取及显式导出结果的跨模块响应。F001 实现前必须在该契约基线中补齐 profile.read、profile.export 和 profile.delete（或记录等价的统一操作）；不得在扩展和本地服务之间另造未登记的消息格式。此项作为实施前检查点，不把契约副本提交到 F001。
5. F001 先支持 loopback HTTP/JSON 的本地开发通道；通道认证、端口和打包细节必须遵守 F004 的最终通信选择。资料领域接口不能依赖某一种传输方式。F004 不得改变 F001 已确定的确认、加密、日志和零远程资料边界。

## Plan of Work

### Phase 0: Research and resolution

- 固定加密 JSON、OS keyring、原子写入和损坏恢复方案；
- 核对共享契约的 ProfileField、Scope、确认和错误语义，列出需要在 PR #1 补齐的读取/导出/删除消息；
- 确认 Options Page 与本地资料服务的职责边界、零远程调用测试方式和脱敏日志规则；
- 将结论写入 research.md，所有技术上下文中的未决项在进入设计前关闭。

### Phase 1: Design and contracts

- 在 data-model.md 固定 Profile、字段定义、字段值、重复记录、范围和导出请求的关系与不变量；
- 在 contracts/profile-lifecycle.md 记录 F001 对共享消息的映射、契约缺口和错误语义；完整 JSON Schema 仍只维护在 packages/contracts；
- 在 quickstart.md 提供无需云端和真实个人资料即可运行的验收路径；
- 复核 Constitution Check，确认加密、确认、日志和跨模块边界没有例外。

### Phase 2: Implementation slices

按 tasks.md 的用户故事顺序实现：

1. 基础项目和契约检查；
2. 纯领域模型与确定性校验；
3. 加密存储、原子提交和故障恢复；
4. Profile API 与 Options Page 的基本编辑闭环；
5. 重复记录、自定义字段、导出和删除；
6. 隐私、性能、可访问性和文档收尾。

每个用户故事先写会失败的验收测试，再实现最小行为；在故事检查点运行独立测试并提交。

## Project Structure

### Documentation (this feature)

    specs/001-profile-library/
    ├── spec.md
    ├── plan.md
    ├── research.md
    ├── data-model.md
    ├── quickstart.md
    ├── contracts/
    │   └── profile-lifecycle.md
    ├── checklists/
    │   ├── requirements.md
    │   └── profile-quality.md
    └── tasks.md

### Source Code (repository root)

    apps/local-agent/
    ├── pyproject.toml
    ├── src/resume_agent/
    │   ├── config.py
    │   ├── api/
    │   │   ├── app.py
    │   │   └── profile_routes.py
    │   ├── profile/
    │   │   ├── models.py
    │   │   ├── errors.py
    │   │   ├── service.py
    │   │   ├── validation.py
    │   │   ├── standard_fields.py
    │   │   ├── export_service.py
    │   │   └── policy.py
    │   ├── storage/
    │   │   ├── base.py
    │   │   ├── encrypted_json.py
    │   │   ├── key_provider.py
    │   │   └── errors.py
    │   └── privacy/
    │       └── redaction.py
    └── tests/
        ├── fixtures/
        │   └── f001_profiles.py
        ├── unit/
        ├── integration/
        ├── performance/
        └── contract/

    apps/extension/
    ├── package.json
    ├── tsconfig.json
    ├── vite.config.ts
    ├── vitest.config.ts
    ├── index.html
    ├── src/options/
    │   ├── main.tsx
    │   ├── ProfilePage.tsx
    │   ├── profileClient.ts
    │   └── components/
    └── tests/options/

    tests/
    ├── fixtures/f001/
    ├── security/
    └── e2e/
        └── f001-profile-library/

packages/contracts/ remains the only shared field and message source; F001 adds no private copy of the master schema.

**Structure Decision**: 采用现有单仓库的 apps/packages/tests 分层。资料领域和加密存储放在 apps/local-agent；用户编辑界面放在 apps/extension/src/options；跨模块契约继续由 packages/contracts 管理；Feature-specific design and validation artifacts remain under specs/001-profile-library. F001 只占用 Options Page 资料维护面，F004 及后续 Feature 负责浏览器运行时页面和动作面。

## API and Security Boundary

- Domain operations are expressed as typed commands: read profile, upsert values, delete values/records, export selected scope.
- Every mutating command carries a user-confirmed decision and an idempotency/request identifier; validation runs before storage.
- The API returns structured success or error information and never returns a secret key, raw storage envelope, or unredacted diagnostic.
- Local service rejects non-loopback origins and oversized requests; exact authentication and transport settings are verified with F004.
- The Options Page never calls a model provider. F001 has no provider dependency and no outbound network client.

## Post-Design Constitution Re-check

- Safety: no submit/navigation/browser action exists in the source tree or command set.
- Privacy: encrypted envelope, key provider isolation, redacted logs and outbound-request test are included in design artifacts.
- Contract/test first: lifecycle contract mapping and failing acceptance tests precede implementation.
- Incremental delivery: US1 is the MVP; US2 and US3 can be demonstrated independently after shared foundation.

## Complexity Tracking

No constitution violations. The encrypted file store, local API and Options Page are the minimum surfaces needed to make manual profile maintenance independently usable; SQLCipher, cloud accounts and Agent orchestration are intentionally deferred.
