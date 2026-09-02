# 项目前置规划：Agent 规范、代码架构与 Git 开发流程

- 更新日期：2026-09-02
- 状态：规划基线，待项目初始化时执行
- 配套产品文档：`docs/product/product-brief-v1.md`

本文规定项目在正式实现前需要准备什么，以及后续如何组织 Agent、代码、Feature 和 Git 历史。它不替代产品范围文档，也不提前锁死具体框架和第三方库。

## 1. 为什么需要 AGENTS.md

需要。根目录的 `AGENTS.md` 用于约束参与本仓库开发的编码 Agent，主要规定：

- 先读哪些文档、哪些文件是权威来源；
- 什么时候可以改代码，什么时候只能讨论或修改规格；
- 分支、提交、测试和 Pull Request 规则；
- 模块边界、数据隐私和安全红线；
- 完成一个 Feature 的最低标准。

它与 Constitution 的分工如下：

| 文件 | 解决的问题 |
| --- | --- |
| 产品基线 | 产品做什么、不做什么 |
| Roadmap | 先做什么、后做什么 |
| Constitution | 项目长期必须遵守的原则 |
| 根目录 `AGENTS.md` | 编码 Agent 应如何工作 |
| 模块级 `AGENTS.md` | 某个模块的局部约束 |
| Feature 的 `spec/plan/tasks` | 当前功能具体如何实现和验收 |

根目录规范先建立即可。等 `apps/extension` 和 `apps/local-agent` 形成稳定模块后，再分别增加模块级 `AGENTS.md`，避免一开始复制大量重复规则。

## 2. 编码 Agent 与运行时 Agent 的区别

### 2.1 编码 Agent

编码 Agent 修改仓库中的代码和文档，必须遵守根目录 `AGENTS.md`、Constitution 和当前 Feature 的规格。它不能因为模型判断就跳过测试、绕过分支流程或修改产品边界。

### 2.2 运行时 Agent

运行时 Agent 是用户使用产品时被按需调用的语义辅助模块。它的约束不能只写在提示词里，还必须由程序强制执行：

- 只能通过有限的、类型明确的操作接口请求插件执行动作；
- 不能直接运行任意脚本或访问不在当前任务范围内的页面；
- 输出必须包含标准字段、候选值、置信度、来源和警告；
- 输出先经过 Policy、Schema 和 Validation 检查，再交给页面执行器；
- 不得自动提交、处理验证码、密码、OTP、签名或支付操作；
- 不得静默新增字段、覆盖已有值或修改资料库；
- 每次调用结束后不保留聊天上下文，不做自主长期记忆。

用户确认后的字段值、网站映射和校验设置可以作为本地配置保存，但它们应当可查看、修改、删除和导出。

## 3. 建议的代码仓库结构

项目采用单仓库，扩展和本地服务分开，跨语言契约集中管理：

```text
/
├─ AGENTS.md
├─ README.md
├─ CONTRIBUTING.md
├─ SECURITY.md
├─ .gitignore
├─ .github/
│  ├─ ISSUE_TEMPLATE/
│  └─ PULL_REQUEST_TEMPLATE.md
├─ .specify/
├─ .agents/
├─ apps/
│  ├─ extension/                 # 浏览器扩展
│  │  ├─ src/
│  │  │  ├─ background/          # 生命周期、消息和权限
│  │  │  ├─ content/             # 页面扫描、字段定位、受控填写
│  │  │  ├─ sidepanel/           # 结果、确认、审校和撤销界面
│  │  │  ├─ options/             # 模型、隐私和用户设置
│  │  │  └─ shared/              # 扩展内部共享类型和工具
│  │  └─ tests/
│  └─ local-agent/               # 本地编排与资料服务
│     ├─ src/
│     │  ├─ api/                 # 本地通信接口
│     │  ├─ orchestrator/        # 当前任务流程状态
│     │  ├─ profile/              # 资料库读写和合并
│     │  ├─ parsing/              # PDF、Word、文本和 OCR
│     │  ├─ normalization/        # 标准字段归类和归一化
│     │  ├─ matching/             # 规则匹配和语义匹配
│     │  ├─ providers/            # DeepSeek/OpenAI-compatible 等模型适配
│     │  ├─ policy/               # 权限、确认和安全策略
│     │  ├─ validation/           # 格式、必填、冲突和风险检查
│     │  ├─ storage/              # 本地加密存储、配置和审计记录
│     │  └─ adapters/             # 用户确认的网站配置接口
│     └─ tests/
├─ packages/
│  ├─ contracts/                 # 标准字段、请求响应和错误契约
│  ├─ fixtures/                  # 脱敏资料、文档和表单样例
│  └─ evals/                     # 解析、识别和填写评测样例
├─ adapters/
│  ├─ examples/                  # 可公开的示例适配配置
│  └─ local/                     # 本机用户配置，不提交真实资料
├─ specs/                         # SDD Feature 规格（每个 Feature 一个目录）
│  └─ 001-profile-library/
│     ├─ spec.md
│     ├─ plan.md
│     └─ tasks.md
├─ docs/
│  ├─ product/                   # 产品 Brief、范围和 Roadmap
│  ├─ architecture/              # 架构说明
│  ├─ adr/                       # 重要技术决策记录
│  └─ discussions/               # 头脑风暴和历史讨论
└─ tests/
   └─ e2e/                       # 扩展 + 本地服务的端到端测试
```

### 3.1 模块依赖规则

- `packages/contracts` 是扩展和本地服务共享的字段与消息事实来源。
- 扩展不得直接调用模型；所有模型请求经过本地服务。
- 页面扫描器只产生页面字段描述，不直接决定资料值。
- Profile 只负责资料，不负责网页 DOM 操作。
- Provider 只负责模型通信，不负责安全决策。
- Policy 是所有高风险动作的统一闸门。
- Parser 产生待确认候选，不直接覆盖已经确认的资料。
- 用户配置和真实个人资料不得进入公开 fixtures 或 Git 历史。

## 4. Git 与 GitHub 工作约定

GitHub 使用 Pull Request；团队口语中的 MR 与 Pull Request 指同一类合并请求。

### 4.1 分支

- `main`：稳定、可运行、可发布。
- `feat/F###-short-name`：一个 Feature 一条分支。
- `fix/short-name`：独立缺陷修复。
- `docs/short-name`：不涉及行为变化的文档修改。
- 不直接向 `main` 推送；一个 Feature 太大时先拆成多个可验收 Feature。

### 4.2 提交节点

在以下节点提交 Git：

- 规格和验收条件完成；
- 一个独立用户故事完成；
- 一个可运行的模块完成；
- 测试补齐并通过；
- 文档或配置完成且与代码一致。

提交信息建议使用清晰的类型和范围，例如：

```text
docs(spec): define profile import acceptance
feat(profile): add manual profile editing
test(parser): cover image-pdf OCR review
fix(fill): preserve existing page values
```

提交不要求每一行改动都单独提交，但每个提交应当可解释、可检查、可回退。

### 4.3 Pull Request / MR

Feature 完成后创建 Pull Request，至少包含：

- 关联的 Feature 规格和任务；
- 已完成的验收标准；
- 测试、类型检查和质量检查结果；
- 已知限制和未纳入范围的内容；
- 涉及隐私或权限变化时的说明。

检查通过并完成审阅后合并到 `main`，再更新 Roadmap 和 Feature 状态。里程碑完成后可以创建版本标签和 GitHub Release。

## 5. 项目级前置工作清单

### 必须先完成

- [ ] 初始化 Git 仓库、GitHub 远程仓库和 `main` 分支保护；
- [ ] 确认根目录 `AGENTS.md`；
- [ ] 创建 `.specify/memory/constitution.md`；
- [ ] 创建总体 Roadmap 和里程碑；
- [ ] 创建 README、CONTRIBUTING 和 SECURITY；
- [ ] 建立扩展与本地服务的最小目录骨架；
- [ ] 定义第一版共享字段和消息契约；
- [ ] 准备脱敏的资料、文档和网页表单样例；
- [ ] 配置最小化的自动检查流程。

### 可以后置

- 具体前端框架和 UI 组件库；
- OCR 引擎和 PDF/Word 解析库；
- 数据库类型和加密实现；
- 模型提示词、置信度阈值和重试参数；
- 复杂控件、附件和多用户服务器；
- 公开网站适配规则的共享方式。

## 6. 后续 Feature 开发循环

每个 Feature 按以下顺序进行：

1. 从 Roadmap 选取一个可独立验收的 Feature；
2. 创建分支或 worktree；
3. 执行 `Specify → Clarify → Plan → Tasks`；
4. 先补测试，再执行实现任务；
5. 在节点完成时提交 Git；
6. 执行测试、验收和 `Converge`；
7. 创建 Pull Request / MR；
8. 审阅通过后合并并更新 Roadmap；
9. 再开始下一个 Feature。

产品级边界发生变化时，先更新产品基线和 Roadmap，再重新评估受影响的 Feature，不在单个分支里偷偷改变总体方向。

## 7. 建议的首批 Feature 顺序

1. 本地资料库：手动录入、编辑和加密存储；
2. 文档资料解析：PDF、Word、图像 PDF OCR、标准化和人工纠正；
3. 浏览器扩展骨架：当前页面扫描和本地服务通信；
4. 标准控件识别与规则优先填写；
5. Agent 语义匹配、不确定字段提示和确认流程；
6. 审校、冲突提示和整次撤销；
7. 自定义字段和用户主动保存的网站配置；
8. 复杂控件、附件、更多浏览器和发布打包。

首个实现目标应形成一个小的端到端闭环，而不是先搭建没有用户价值的大型基础设施。后续 Feature 再逐步扩大页面覆盖和自动化程度。
