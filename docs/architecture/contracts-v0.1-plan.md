# 共享契约 v0.1 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task with verification checkpoints.

**Goal:** 建立扩展与本地 Agent 共用的、可机器校验的 JSON Schema Draft 2020-12 契约 v0.1，并用脱敏示例和测试固定安全边界。

**Architecture:** 以 `packages/contracts/v0.1/contracts.schema.json` 作为唯一主 Schema，所有消息类型放在同一文件的 `$defs` 中，通过 `$ref` 复用公共类型。扩展和 Agent 只交换声明式数据：候选、审查决定、填写动作和逐动作结果；Schema 明确禁止提交动作和未经确认的高风险操作。

**Tech Stack:** JSON Schema Draft 2020-12；Python 3.11；`jsonschema` 做契约校验；`pytest` 做回归测试。

## Global Constraints

- 契约版本固定为 `0.1`，每个跨边界请求/响应包含 `schema_version`、`request_id` 和 `task_id`。
- 扩展负责当前页面读取、受控填写、结果展示和撤销；本地 Agent 负责解析、标准化、匹配、策略校验和本地资料存储。
- 不定义提交申请、点击最终确认、验证码、OTP、签名、支付或任意脚本动作。
- 网页已有值默认不覆盖；不确定字段必须显式候选、置信度、来源、警告和确认要求。
- 真实个人资料、API Key、网站配置和未经脱敏的文档不得进入仓库或示例。
- 传输方式、框架、数据库、OCR 引擎和 DOM 算法不在本计划中决定。

---

### Task 1: 建立契约测试基线

**Files:**
- Create: `tests/contracts/test_contract_schemas.py`
- Modify: `tests/README.md`（补充契约测试入口）

**Interfaces:**
- Consumes: 计划中的主 Schema 路径和 `$defs` 名称。
- Produces: 可独立运行的 Schema 完整性、安全不变量和示例校验测试。

- [x] **Step 1: 写失败测试**

  覆盖以下行为：主 Schema 存在且是 Draft 2020-12；代表性示例引用的 `$defs` 存在；安全字段 `auto_submit`/`submitted` 必须为 `false`；审查决定必须是明确用户确认；需要确认的候选不能声明为无需确认。

- [x] **Step 2: 运行测试确认 RED**

  运行：`python -m pytest tests/contracts/test_contract_schemas.py -q`

  预期：因主 Schema 和示例尚未创建而失败，不能是测试收集错误。

### Task 2: 实现主 Schema

**Files:**
- Create: `packages/contracts/v0.1/contracts.schema.json`

**Interfaces:**
- Consumes: Task 1 中测试锁定的 `$defs` 名称。
- Produces: `Profile*`、`Scan*`、`Match*`、`Fill*`、`Review*`、`Undo*`、`Error*` 消息定义。

- [x] **Step 1: 添加公共类型和严格对象约束**

  定义不透明 ID、版本、字段类型、来源、置信度、敏感级别、定位器、警告和页面上下文；跨模块对象默认 `additionalProperties: false`。

- [x] **Step 2: 添加资料、扫描、匹配消息**

  固定标准字段 ID 与自定义字段兼容的 `ProfileField`，并定义导入预览、页面字段扫描、匹配候选及不支持字段的结构。

- [x] **Step 3: 添加审查、填写、撤销和错误消息**

  填写动作只允许声明式控件操作；`FillPlan.auto_submit`、`ExecutionResult.submitted` 使用 `const: false`；`ReviewDecision.user_confirmed` 使用 `const: true`；结果按动作报告状态并携带撤销令牌。

### Task 3: 添加脱敏示例和开发者说明

**Files:**
- Create: `packages/contracts/v0.1/README.md`
- Create: `packages/contracts/v0.1/examples/*.json`（覆盖资料、扫描、匹配、填写、审查、撤销、错误请求/响应）
- Create: `docs/adr/0001-json-schema-shared-contract.md`
- Modify: `packages/contracts/README.md`

**Interfaces:**
- Consumes: Task 2 的 `$defs` 和逻辑操作目录。
- Produces: 可供扩展、Agent 和测试共同使用的最小 JSON 示例及版本兼容说明。

- [x] **Step 1: 为每个主要操作写脱敏 JSON**

  示例只使用占位姓名、域名和文档引用，不写真实身份证号、手机号、地址、Token 或 API Key。

- [x] **Step 2: 写版本和兼容规则**

  说明 `0.1` 的字段语义、未知字段处理、禁止新增提交动作的规则，以及后续破坏性变更如何升主版本。

### Task 4: 完整验证并提交

**Files:**
- Modify: `docs/architecture/ui-and-module-boundaries-v0.1.md`（仅在契约名称或约束需要对齐时更新）
- Modify: `docs/product/roadmap.md`（记录当前审阅状态）

**Interfaces:**
- Consumes: Task 1–3 的全部文件。
- Produces: 可审阅的架构基线、通过的测试和独立 Git 提交。

- [x] **Step 1: 运行完整契约测试**

  运行：`python -m pytest tests/contracts -q`

- [x] **Step 2: 做敏感信息和安全不变量审计**

  检查示例和 Schema 不含 API Key/真实个人资料，且仓库中没有 `auto_submit: true` 或 `submitted: true`。

- [x] **Step 3: 检查差异并提交**

  运行 `git diff --check` 和 `git status --short`，确认只包含本 Feature 文件后提交：`git commit -m "feat(contracts): define v0.1 shared message contracts"`。

- [x] **Step 4: 推送独立分支**

  推送 `docs/contracts-v0.1` 到远程，保留后续 Pull Request 审阅入口；不直接合并到 `main`。

---

### Task 5: 补齐 F001 资料生命周期契约

**Files:**
- Modify: `packages/contracts/v0.1/contracts.schema.json`
- Modify: `packages/contracts/v0.1/README.md`
- Create: `packages/contracts/v0.1/CHANGELOG.md`
- Create: `packages/contracts/v0.1/examples/profile-read.json`
- Create: `packages/contracts/v0.1/examples/profile-read-response.json`
- Create: `packages/contracts/v0.1/examples/profile-delete.json`
- Create: `packages/contracts/v0.1/examples/profile-delete-response.json`
- Create: `packages/contracts/v0.1/examples/profile-export.json`
- Create: `packages/contracts/v0.1/examples/profile-export-response.json`
- Create: `tests/contracts/test_profile_lifecycle_contracts.py`

**Interfaces:**
- Consumes: `RequestEnvelope`、`ResponseEnvelope`、`ProfileField`、`Warning` 和 `ErrorResponse`。
- Produces: `ProfileReadRequest/Response`、`ProfileDeleteRequest/Response`、`ProfileExportRequest/Response`，以及资料快照、重复记录、字段定义、显式选择范围和乐观版本字段。

- [x] **Step 1: 写失败的生命周期契约测试**

  测试先锁定以下行为：六个请求/响应定义和示例存在；读取不要求确认且不能携带写入字段；删除和导出必须明确确认并带预期资料版本；空选择被拒绝；完整删除不能与局部选择混用；导出只能写入用户选择的本地文件，响应不能包含文件内容或上传地址。

- [x] **Step 2: 运行新增测试确认 RED**

  运行：`python -m pytest tests/contracts/test_profile_lifecycle_contracts.py -q`

  预期：因 `ProfileReadRequest` 等定义和示例尚不存在而失败，现有 33 个测试仍保持通过。

- [x] **Step 3: 添加资料生命周期公共类型和消息**

  增加资料修订号、字段定义、已确认字段、重复记录、资料快照、删除选择、导出选择和本地导出目标。`profile.upsert` 同步携带 `profile_id`、`expected_profile_version`，响应返回新的 `profile_version`，避免 F001 私下增加版本字段。

- [x] **Step 4: 添加脱敏示例、错误码和版本记录**

  六个新示例只使用合成数据；README 更新操作表、确认规则和稳定错误码；CHANGELOG 说明这些新增是 v0.1 内尚未发布的向后兼容契约补充。资料导出响应只返回状态和显示文件名，不返回明文内容或远程 URL。

- [x] **Step 5: 完整验证并更新 PR #1**

  运行新增测试、全部契约测试、主 Schema 校验、敏感信息扫描和 `git diff --check`。验证通过后提交并推送 `docs/contracts-v0.1`，让现有 PR #1 自动更新；不直接合并到 `main`。
