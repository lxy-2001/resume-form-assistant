# 智能简历填写助手

一个本地优先的网页表单填写助手：浏览器扩展负责识别和受控填写当前页面，本地服务负责资料解析、规则校验和按需调用 Agent。

## 当前状态

项目仍处于基础设施初始化阶段。产品边界、标准字段、验收标准、架构和开发流程已记录在以下文档：

- `docs/product/product-brief-v1.md`
- `docs/product/roadmap.md`
- `docs/architecture/project-foundation-and-workflow.md`
- `docs/architecture/ui-and-module-boundaries-v0.1.md`
- `packages/contracts/v0.1/README.md`
- `docs/discussions/2026-09-01-smart-resume-form-agent-discussion.md`
- `AGENTS.md`
- `.specify/memory/constitution.md`

## 设计原则

- 规则优先，Agent 处理需要语义理解的部分；
- 本地优先，远程模型调用需用户同意；
- 不确定字段不静默填写；
- 已有网页内容默认不覆盖；
- 所有填写可审阅、修改和撤销；
- 永远不自动提交申请。

## 开发方式

每个可独立验收的 Feature 使用独立分支，按 `Specify → Clarify → Plan → Tasks → Implement → Converge` 推进，完成后通过 GitHub Pull Request 合并到 `main`。详见 `AGENTS.md` 和 Roadmap。

真实个人资料、API Key 和本地配置不得提交到仓库。
