# UI 与模块边界、共享契约基线 v0.1

- 更新日期：2026-09-02
- 状态：已批准的首版架构基线；契约实现待 Pull Request 审阅
- 关联 Roadmap：M0 / F000A

本文固定首版跨模块不能随意改变的边界、界面职责、数据流和消息契约。它不锁定 React/Vue、FastAPI、OCR 引擎、DOM 算法或具体加密库；这些实现选择在对应 Feature 的 `plan.md` 中决定。

## 1. 总体边界

```text
浏览器扩展（网页执行端）
  ├─ Content Script：读取当前页面、执行受控填写、记录页面撤销信息
  ├─ Background：权限、消息路由、本地服务会话和任务生命周期
  ├─ Side Panel：当前页面的扫描、候选、确认、预览、填写和撤销
  └─ Options Page：资料库、文件导入、模型和隐私设置

本地 Agent 服务（决策与资料端）
  ├─ API：接收扩展请求并返回结构化结果
  ├─ Orchestrator：编排当前任务状态，不做长期对话记忆
  ├─ Profile/Storage：资料读写、加密和本地配置
  ├─ Parsing/Normalization：PDF、Word、OCR、标准化和纠正候选
  ├─ Matching：规则匹配和受限的语义匹配
  ├─ Provider：DeepSeek/OpenAI-compatible 模型通信
  ├─ Policy/Validation：确认、敏感级别、格式和安全闸门
  └─ Adapters：用户主动保存的网站映射配置
```

核心原则：扩展可以执行网页动作，但不能自行决定高风险动作；Agent 可以提出结构化候选，但不能直接操作 DOM。所有跨模块数据以 `packages/contracts/v0.1/contracts.schema.json` 为唯一事实来源。

## 2. 界面职责

### 2.1 Options Page：资料和全局设置

Options Page 是一个可打开的扩展配置页面（完整浏览器标签页），首版包含：

- 标准字段的手动新增、编辑和删除；
- PDF、Word、文本和图像型 PDF 的导入入口；
- 解析候选、来源、置信度、疑问和纠正确认；
- 模型 Provider、远程调用同意和隐私设置；
- 敏感字段必须确认列表；
- 已确认的网站映射查看、修改和删除。

Options Page 只是界面客户端。个人资料、解析结果和网站配置由本地 Agent 保存；扩展不把完整资料作为自己的长期存储副本。文件导入先由本地 Agent 解析，未确认的候选不得写入资料库。

### 2.2 Side Panel：当前网页任务

Side Panel 只处理用户当前主动启动的页面任务：

1. 显示当前页面/当前步骤的扫描状态；
2. 列出已识别、未识别和不支持的字段；
3. 显示候选值、来源、置信度、采用理由和警告；
4. 让用户接受、修改、跳过或拒绝单个候选；
5. 在执行前预览变化，在执行后显示结果；
6. 提供整次撤销入口。

Side Panel 不承载完整资料编辑，也不直接调用模型。用户自行点击多步骤表单的“下一步”；进入新步骤后重新扫描。

### 2.3 Popup 与设置入口

Popup 只作为快捷入口（打开 Side Panel、打开 Options Page、显示本地服务状态），不放复杂表单和长文本编辑，避免窗口关闭造成状态丢失。

## 3. 模块职责与禁止事项

| 模块 | 允许负责 | 明确不负责 |
| --- | --- | --- |
| Content Script | 读取可访问 DOM、定位字段、执行契约中的填写动作、记录前后值 | 调用模型、读取完整资料库、点击提交/下一步、执行任意脚本 |
| Background | 权限、消息转发、任务 ID、会话和本地服务连接 | 语义匹配、直接保存个人资料、绕过页面安全机制 |
| Side Panel | 展示和收集用户决定、预览、撤销请求 | 直接访问 Provider、静默确认候选、自动导航 |
| Options Page | 资料编辑、导入确认、全局设置 | 直接操作第三方网页、直接调用模型 |
| Agent API/Orchestrator | 接收请求、编排当前任务、返回结构化结果 | 直接操作浏览器 DOM、自动提交、长期自主记忆 |
| Profile/Storage | 本地加密资料、配置和审计记录 | 写入 Git、输出真实资料到普通日志 |
| Parser/Normalizer | 产生带来源和置信度的待确认候选 | 未经确认覆盖资料库或修改字段定义 |
| Provider | 按同意范围发送最少内容并返回模型结果 | 决定权限、执行网页动作、绕过 Policy |
| Policy/Validation | 统一确认、敏感、格式、冲突和提交禁止检查 | 被 UI 或提示词绕过 |

## 4. 首版数据流

### 4.1 资料录入和导入

```text
Options Page
  → profile.upsert / profile.import.preview
  → 本地 Agent Parser、Normalizer、Validation
  → 候选（来源、置信度、疑问）
  → 用户确认/纠正
  → profile.import.confirm / profile.upsert
  → 本地加密资料库
```

远程模型调用默认关闭。用户同意后，Provider 只能收到完成当前解析所需的最少内容；敏感字段仍受 Policy 闸门控制。

### 4.2 当前网页填写

```text
用户点击启动
  → Content Script 扫描当前页面
  → Background 生成 page.scan 请求
  → Agent 规则匹配，必要时按同意调用 Provider
  → MatchCandidate / FillPlan
  → Side Panel 展示并等待用户决定
  → Policy + Validation 检查
  → Content Script 执行 FillAction
  → ExecutionResult + 可撤销记录
```

已有网页值默认不覆盖。冲突时必须同时显示原值和建议值并等待用户决定。任何契约都没有“提交申请”动作；`auto_submit` 和 `submitted` 在 v0.1 中固定为 `false`。

## 5. v0.1 共享接口约束

### 5.1 通用约定

- 契约格式：JSON Schema Draft 2020-12；主文件为 `contracts.schema.json`；版本字符串固定为 `0.1`。
- 所有请求/响应包含 `schema_version`、`request_id` 和 `task_id`；ID 是不透明字符串，不能由另一模块自行重新解释。
- Agent 返回候选或声明式动作，不返回 JavaScript、CSS 片段或可执行脚本。
- 置信度、来源、警告、敏感级别和用户确认状态必须显式表达，不能藏在自由文本中。
- 传输层暂不锁定。F004 在 loopback HTTP/JSON 与 Native Messaging 中做小范围验证后选择一种实现，但必须保持本契约不变。
- 无论采用哪种传输，服务只接受本机扩展请求，必须有会话认证、请求超时和大小限制，不对公网监听。

### 5.2 逻辑操作目录

| 操作 | 请求方 → 处理方 | 主要契约定义 |
| --- | --- | --- |
| `profile.upsert` | Options Page → Agent | `ProfileUpsertRequest` / `ProfileUpsertResponse` |
| `profile.import.preview` | Options Page → Agent | `ProfileImportPreviewRequest` / `ProfileImportPreview`（响应） |
| `profile.import.confirm` | Options Page → Agent | `ProfileImportConfirmRequest` / `ProfileImportConfirmResponse` |
| `page.scan` | Background → Agent | `ScanRequest` / `ScanResponse` |
| `page.match` | Background → Agent | `MatchRequest` / `MatchResponse` |
| `review.submit` | Side Panel → Agent | `ReviewDecision` / `ReviewDecisionResponse` |
| `fill.execute` | Background → Content Script | `FillPlan` / `ExecutionResult` |
| `fill.undo` | Side Panel → Content Script | `UndoRequest` / `UndoResult` |
| 错误 | 任意边界 | `ErrorResponse`（内含 `Error`） |

逻辑操作名是跨模块约束；实际 URL、端口、消息通道和序列化代码由 F004 的实现计划决定。

## 6. 任务状态和失败处理

```text
idle
  → scanning
  → candidates_ready
  → awaiting_user_review
  → executing
  → completed / partial / failed
  → undoable（在有可恢复动作时）
```

- 用户取消、页面离开或服务超时必须结束当前任务，不得继续后台填写；
- 某个字段失败不能伪装成成功，结果必须逐动作报告；
- 不支持的控件进入 `unsupported`，提供人工处理入口；
- 模型不可用时，规则能够继续处理简单字段，复杂字段标为待人工处理；
- 重试不得重复执行已成功的动作，使用 `request_id`、`task_id` 和动作 ID 去重。

## 7. 暂不在基线中锁定的内容

- 前端框架、组件库和视觉设计；
- 本地 Agent 的 Web 框架、数据库和加密库；
- PDF/Word/OCR 引擎；
- DOM 定位和动态页面算法；
- 模型提示词、阈值和重试参数；
- 打包、自动更新和多浏览器细节。

这些选择必须在对应 Feature 的 `plan.md` 中比较方案，并以测试和小型验证结果为依据；如果改变了本文的职责、契约或安全边界，必须新增 ADR 并更新本文件。

## 8. 基线验收条件

- [x] Options Page 与 Side Panel 的职责不重叠；
- [x] 扩展、Agent、Provider、Policy 的边界明确；
- [x] 资料录入、网页扫描、匹配、填写和撤销的数据流明确；
- [x] 共享契约有唯一版本来源和逻辑操作目录；
- [x] 契约禁止自动提交和任意脚本动作；
- [x] 具体实现细节被明确留给 Feature 计划。
