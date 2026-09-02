<!--
Sync Impact Report
- Version change: unversioned Spec Kit scaffold → 1.0.0
- Modified principles: replaced five scaffold placeholders with project principles:
  user-controlled safety, deterministic-first bounded Agent, local-first privacy,
  contract/test-first, and incremental traceable delivery.
- Added sections: Additional Constraints; Development Workflow.
- Removed sections: none; scaffold placeholders were replaced with project-specific content.
- Follow-up TODOs: none.
-->

# 智能简历填写助手 Constitution

## Core Principles

### I. User-Controlled Safety and Reversibility

所有网页操作必须由用户主动启动，并且必须经过受控的动作接口。系统不得自动提交申请、点击最终确认、绕过验证码、OTP、签名、支付或反爬机制。不确定字段、敏感字段、长文本生成和新增永久字段必须进入人工确认流程。已有网页内容默认不覆盖；每次填写必须提供可追踪结果和整次撤销能力。这样可以把用户的最终控制权和错误可恢复性作为不可破坏的产品约束。

### II. Deterministic-First, Bounded Agent

简单、明确且可验证的字段必须优先由本地规则、标准字段契约和确定性校验处理；只有规则无法判断的语义匹配、文档归类、候选生成和复杂审校才调用 Agent。运行时 Agent 只能返回符合共享契约的结构化候选、置信度、来源和警告，不能直接执行任意代码、静默改变字段定义或绕过 Policy 层。模型不可用时，简单字段仍必须能够工作。

### III. Local-First Privacy and Least Privilege

个人资料、解析结果、用户纠正、API Key 和网站配置默认只保存在本地加密存储中。远程模型调用必须由用户明确同意，并且只发送完成当前任务所需的最少内容；普通日志、测试样例和 Git 历史不得包含真实个人资料或密钥。扩展、本地服务、解析器和模型 Provider 只能访问完成当前任务所必需的数据和权限。

### IV. Contract- and Test-First

扩展与本地服务共用的数据格式、字段含义、请求响应和错误语义必须以 `packages/contracts/` 为唯一事实来源。任何契约变化都必须补充相应的契约测试和迁移说明。行为变化必须先由能够表达验收条件的测试描述，再实现最小行为，并在 Feature 合并前完成单元、集成或端到端验证。

### V. Incremental and Traceable Feature Delivery

项目必须按可独立验收的 Feature 增量交付，不把整个产品写成一个巨型 Feature。每个 Feature 必须拥有 `spec.md`、`plan.md` 和 `tasks.md`，使用独立分支，经过有意义节点提交、验证和 GitHub Pull Request 审阅后才能合并到 `main`。产品范围、架构决策和验收结果必须写入仓库文档，不能只依赖聊天记录。

## Additional Constraints

- 首版目标是常见、可访问的网页表单和标准 HTML 控件；系统必须显式报告无法识别的页面或控件，不得承诺所有网站百分之百兼容。
- 资料入口必须支持手动录入，以及 PDF、Word、文本和图像型 PDF OCR；解析结果先进入待确认状态，再写入资料库。
- 标准字段是稳定的语义标识，不是每个网站或用户都必须填写的字段；自定义字段可以通过用户确认流程增加。
- 多步骤表单由用户点击下一步，系统只处理当前页面或当前步骤；不得自动跨步骤导航。
- 首版不做招聘公告分析、批量投递、自动提交、验证码处理、密码/支付操作或多用户云端同步。
- 用户确认后的字段映射或网站配置属于可查看、可修改、可删除的普通本地配置，不属于 Agent 的自主长期记忆。
- 运行时 Agent 的所有输出必须经过 Schema、Policy 和 Validation 检查；提示词不能替代程序安全边界。

## Development Workflow

1. 产品级变更先更新 `docs/product/` 中的产品基线和 Roadmap，并评估受影响的 Feature。
2. 每个 Feature 按 `Specify → Clarify → Plan → Checklist → Tasks → Analyze → Implement → Converge` 执行；不提前为未选中的 Feature 构建复杂基础设施。
3. 每个 Feature 使用 `feat/F###-short-name` 分支；不直接向 `main` 推送。提交应对应可解释、可验证的节点。
4. Feature 完成后必须验证任务、测试、权限、失败处理和验收标准，再创建 Pull Request；审阅和 CI 通过后合并，并更新 Roadmap。
5. 规格、计划、任务、代码和测试出现不一致时，以用户当前要求和已批准的产品文档为准，并在同一变更中修正文档。

## Governance

本 Constitution 是项目级治理基线，适用于所有 Feature、代码、测试和文档。任何例外都必须在对应 Feature 或 ADR 中说明原因、影响、替代方案和回滚方式，并经过 Pull Request 审阅。

修订 Constitution 必须：

- 提交包含版本变更、修改原则、影响范围和迁移说明的 Pull Request；
- 按语义化版本递增：原则或治理范围的兼容性破坏为 MAJOR，新增或实质扩展原则为 MINOR，纯澄清或修订文字为 PATCH；
- 在合并前检查所有受影响的 Feature 规格、AGENTS.md 和自动检查；
- 更新本文顶部的 Sync Impact Report、版本和日期。

所有编码 Agent 必须先阅读本 Constitution、根目录 `AGENTS.md` 和当前 Feature 文档，再修改代码。若无法证明某项改动符合本 Constitution，必须暂停并请求澄清，而不是自行放宽约束。

**Version**: 1.0.0 | **Ratified**: 2026-09-02 | **Last Amended**: 2026-09-02