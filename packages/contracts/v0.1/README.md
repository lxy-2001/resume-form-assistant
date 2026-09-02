# Shared Contracts v0.1

这是浏览器扩展与本地 Agent 之间的唯一共享数据契约。主文件是
[`contracts.schema.json`](contracts.schema.json)，格式为 JSON Schema Draft 2020-12。

## 使用方式

实现方应将主 Schema 注册到自己的 JSON Schema 校验器，然后通过 `$ref` 指向对应的
`$defs` 定义。v0.1 不要求某一种传输方式；loopback HTTP/JSON、Native Messaging
或测试内存通道都必须传递同样的消息结构。

所有请求和响应都带有：

- `schema_version`：固定为 `"0.1"`；
- `request_id`：本次消息的不透明 ID；
- `task_id`：当前页面或资料处理任务的不透明 ID；
- `operation`：逻辑操作名及其 `.result` 响应名。

## 操作目录

| 操作 | 请求定义 | 响应定义 |
| --- | --- | --- |
| 资料写入 | `ProfileUpsertRequest` | `ProfileUpsertResponse` |
| 资料导入预览 | `ProfileImportPreviewRequest` | `ProfileImportPreview` |
| 资料导入确认 | `ProfileImportConfirmRequest` | `ProfileImportConfirmResponse` |
| 页面扫描 | `ScanRequest` | `ScanResponse` |
| 页面匹配 | `MatchRequest` | `MatchResponse` |
| 用户审查 | `ReviewDecision` | `ReviewDecisionResponse` |
| 执行填写 | `FillPlan` | `ExecutionResult` |
| 整次撤销 | `UndoRequest` | `UndoResult` |
| 失败响应 | — | `ErrorResponse` |

公共类型（例如 `ProfileField`、`PageField`、`MatchCandidate`、`FillAction`、
`Warning` 和 `Consent`）也位于主 Schema 的 `$defs` 中，避免扩展和 Agent 各自
解释字段含义。

## 安全不变量

- `FillAction` 只允许声明式的文本、日期、数字、选择和勾选操作，不接收 JavaScript、
  CSS 或脚本字符串。
- `FillPlan.auto_submit` 和 `ExecutionResult.submitted` 在 v0.1 中固定为 `false`；
  契约没有提交申请、下一步、验证码、OTP、签名、支付或密码操作。
- `ProfileUpsertRequest.user_confirmed`、`ReviewDecision.user_confirmed`、`ImportDecision.user_confirmed`、`UndoRequest.user_confirmed`
  和已执行动作的 `approved` 必须为 `true`。
- 敏感或高敏感候选必须进入 `needs_confirmation`；不确定候选必须携带置信度、来源、
  理由和警告。
- `PageField.current_value_present` 用于保护已有网页内容；如果已有值，执行动作应
  携带匹配的 `Precondition`，由执行端在写入前再次检查。
- 远程模型调用通过 `Consent` 表示。没有用户同意时，`remote_model_allowed` 必须为
  `false`，并且响应不得声称发送了远程资料。

## 示例

`examples/` 中的文件都是可公开提交的脱敏消息：

- `profile-upsert.json` / `profile-upsert-response.json`：手动写入资料字段及结果；
- `profile-import-preview-request.json` / `profile-import-preview.json`：文件导入预览（可覆盖 OCR 场景）；
- `profile-import-confirm.json` / `profile-import-confirm-response.json`：用户确认解析候选后写入资料库；
- `scan-request.json` / `scan-response.json`：扫描当前页面的标准 HTML 控件；
- `match-request.json` / `match-response.json`：规则自动填写候选和需要人工确认的敏感候选；
- `fill-plan.json`：经用户确认后的声明式填写计划；
- `review-decision.json` / `review-decision-response.json`：用户修改并确认候选及结果；
- `execution-result.json`：逐动作结果和撤销令牌；
- `undo-request.json` / `undo-result.json`：整次撤销；
- `error-response.json`：结构化失败响应。

## 版本策略

v0.1 处于首版开发阶段。向后兼容的新增可选字段可以继续使用 `0.1`，但必须同步
更新 Schema、示例和测试；改变既有字段语义、删除字段或新增高风险动作时，应提升
主版本并建立 ADR。未知字段在严格校验器中被拒绝，避免扩展和 Agent 静默产生不同解释。

真实个人资料、API Key、未脱敏文档、网站配置和运行日志不属于此目录，不能写入 Git。

## 直接校验与隐私记录

主 Schema 顶层的 `oneOf` 已列出全部跨边界消息，因此实现方既可以直接校验
`contracts.schema.json`，也可以按 `$defs/<DefinitionName>` 只校验某一种消息。导入和匹配
响应都要求 `consent_recorded`：远程发送时必须同时给出 Provider 和 `true`，本地处理时
应给出 `false`。响应中的 `provider`、`details` 和警告不得包含原始个人资料；它们只用于
可审计的状态和错误信息。

下列能力不在 v0.1 消息目录中，等对应 Feature 冻结需求后再增加独立契约：长文本生成与
审校建议、网站适配配置 CRUD、复杂控件/附件、跨步骤导航和多用户同步。这样可以先让
F001–F009 共用稳定边界，避免为尚未实现的功能提前锁定协议。