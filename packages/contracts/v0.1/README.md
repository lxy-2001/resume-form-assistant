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
| 资料读取 | `ProfileReadRequest` | `ProfileReadResponse` |
| 资料写入 | `ProfileUpsertRequest` | `ProfileUpsertResponse` |
| 资料删除 | `ProfileDeleteRequest` | `ProfileDeleteResponse` |
| 资料导出 | `ProfileExportRequest` | `ProfileExportResponse` |
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

`ProfileUpsertRequest.delete_field_ids` 保留用于一次编辑中原子地“改字段并删字段”；
独立的删除流程（记录、自定义字段定义或全部资料）使用 `profile.delete`，以便统一确认、
版本冲突和部分清理结果。

删除或导出选择中的 `field_ids` 是按字段 ID 的宽选择，会覆盖该字段存在的所有范围。
当同一字段在多个范围并存、而用户只想处理其中一个值时，使用 `field_values`，其中每项必须
包含 `id` 和 `scope`，website/application 还必须包含 `scope_context`。这两个选择方式不能
在同一请求中混用。

## 安全不变量

- `FillAction` 只允许声明式的文本、日期、数字、选择和勾选操作，不接收 JavaScript、
  CSS 或脚本字符串。
- `FillPlan.auto_submit` 和 `ExecutionResult.submitted` 在 v0.1 中固定为 `false`；
  契约没有提交申请、下一步、验证码、OTP、签名、支付或密码操作。
- `ProfileUpsertRequest.user_confirmed`、`ProfileDeleteRequest.user_confirmed`、`ProfileExportRequest.user_confirmed`、`ReviewDecision.user_confirmed`、`ImportDecision.user_confirmed`、`UndoRequest.user_confirmed`
  和已执行动作的 `approved` 必须为 `true`。
- 资料写入、删除和导出必须携带 `profile_id` 与 `expected_profile_version`；版本不一致时返回
  `STALE_PROFILE_VERSION`，不得静默覆盖较新的资料。
- 空资料的 `profile_version` 从 `0` 开始；每次成功写入或删除只增加一次。读取和导出不改变
  版本，响应返回本次操作所使用或产生的版本。
- 已保存的 `ProfileField` 必须带确认、来源和更新时间；`website`/`application` 范围必须带
  `scope_context`，`global` 范围禁止携带该上下文。
- 删除必须给出明确的字段、记录、自定义字段定义或完整资料选择；完整删除不能与局部选择混用。
- 导出只允许用户确认的 `local_file` 目标，并拒绝 URL 和网络共享路径；成功响应只报告状态和显示文件名，不返回资料内容或上传 URL。
- 敏感或高敏感候选必须进入 `needs_confirmation`；不确定候选必须携带置信度、来源、
  理由和警告。
- `PageField.current_value_present` 用于保护已有网页内容；如果已有值，执行动作应
  携带匹配的 `Precondition`，由执行端在写入前再次检查。
- 远程模型调用通过 `Consent` 表示。没有用户同意时，`remote_model_allowed` 必须为
  `false`，并且响应不得声称发送了远程资料。

## 示例

`examples/` 中的文件都是可公开提交的脱敏消息：

- `profile-upsert.json` / `profile-upsert-response.json`：手动写入资料字段及结果；
- `profile-read.json` / `profile-read-response.json`：读取当前资料快照及显式空状态；
- `profile-delete.json` / `profile-delete-response.json`：确认后删除明确选择的资料及结果；
- `profile-export.json` / `profile-export-response.json`：确认后导出所选资料到本地文件及结果；
- `profile-import-preview-request.json` / `profile-import-preview.json`：文件导入预览（可覆盖 OCR 场景）；
- `profile-import-confirm.json` / `profile-import-confirm-response.json`：用户确认解析候选后写入资料库；
- `scan-request.json` / `scan-response.json`：扫描当前页面的标准 HTML 控件；
- `match-request.json` / `match-response.json`：规则自动填写候选和需要人工确认的敏感候选；
- `fill-plan.json`：经用户确认后的声明式填写计划；
- `review-decision.json` / `review-decision-response.json`：用户修改并确认候选及结果；
- `execution-result.json`：逐动作结果和撤销令牌；
- `undo-request.json` / `undo-result.json`：整次撤销；
- `error-response.json`：结构化失败响应。

## 资料生命周期错误码

生命周期操作失败继续使用统一 `ErrorResponse`，并通过 `failed_operation` 指明失败的
`profile.read`、`profile.upsert`、`profile.delete` 或 `profile.export`。可用的稳定错误码为：

| 错误码 | 含义 |
| --- | --- |
| `PROFILE_NOT_FOUND` | 指定资料不存在 |
| `CONFIRMATION_REQUIRED` | 写入、删除或导出缺少明确确认 |
| `STALE_PROFILE_VERSION` | 预期资料版本与当前版本不一致 |
| `INVALID_PROFILE_SELECTION` | 删除或导出范围为空、冲突或无效 |
| `INVALID_FIELD_VALUE` | 字段值未通过类型或格式校验 |
| `CUSTOM_FIELD_CONFLICT` | 自定义字段与既有定义冲突 |
| `STORAGE_UNAVAILABLE` | 本地资料存储暂时不可用 |
| `STORAGE_CORRUPT_OR_UNRECOVERABLE` | 加密资料损坏或密钥不可恢复 |
| `EXPORT_CANCELLED` / `EXPORT_FAILED` | 导出被用户取消或执行失败 |
| `DELETE_FAILED` / `DELETE_PARTIAL` | 删除失败，或文件与密钥清理只有部分完成 |

错误消息和 `details` 不得回显资料值、导出内容、密钥或完整本地路径。用户在确认界面取消时
通常不发送变更请求；如果本地文件选择器已经产生请求后取消，可使用 `EXPORT_CANCELLED`。

## 版本策略

v0.1 处于尚未发布的首版开发阶段。PR #1 合并前可以补齐 F001 已确认需要的必填字段，
但必须在同一 PR 中同步 Schema、示例和测试。v0.1 发布后，向后兼容的新增可选字段可以
继续使用 `0.1`；新增必填字段、改变既有字段语义、删除字段或新增高风险动作时必须提升
契约版本并建立迁移说明，必要时新增 ADR。未知字段在严格校验器中被拒绝，避免扩展和
Agent 静默产生不同解释。

真实个人资料、API Key、未脱敏文档、网站配置和运行日志不属于此目录，不能写入 Git。
本版本的增量记录见 [`CHANGELOG.md`](CHANGELOG.md)。

## 直接校验与隐私记录

主 Schema 顶层的 `oneOf` 已列出全部跨边界消息，因此实现方既可以直接校验
`contracts.schema.json`，也可以按 `$defs/<DefinitionName>` 只校验某一种消息。导入和匹配
响应都要求 `consent_recorded`：远程发送时必须同时给出 Provider 和 `true`，本地处理时
应给出 `false`。响应中的 `provider`、`details` 和警告不得包含原始个人资料；它们只用于
可审计的状态和错误信息。

下列能力不在 v0.1 消息目录中，等对应 Feature 冻结需求后再增加独立契约：长文本生成与
审校建议、网站适配配置 CRUD、复杂控件/附件、跨步骤导航和多用户同步。这样可以先让
F001–F009 共用稳定边界，避免为尚未实现的功能提前锁定协议。
