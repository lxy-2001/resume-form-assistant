# Implementation Plan: 文档资料解析与确认导入

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task with verification checkpoints.

**Goal:** 将本地 PDF、DOCX 和图像型 PDF 解析结果安全地接入 F001 资料库的人工确认流程。

**Architecture:** 文件输入和解析只产生短生命周期的文档片段；候选生成层把片段映射到共享标准字段；确认层复用 F001 的版本校验、敏感字段策略和持久化。扩展通过现有共享契约展示预览和收集决定，本地服务不把解析结果直接写入资料库。

**Tech Stack:** 现有 Python 本地服务、React/Vite Options Page、JSON Schema v0.1、脱敏 PDF/DOCX/OCR 测试夹具。具体解析库和 OCR 引擎在 Phase 0 小验证后确定。

## Global Constraints

- 首版只支持 PDF 和 DOCX；`.doc` 明确拒绝。
- 预览候选始终需要用户确认，不能直接覆盖 F001 资料。
- 默认本地处理；远程模型必须有明确同意和最小数据范围。
- 不新增自动提交、网页导航、验证码、OTP、签名、支付、云端同步或长期记忆。
- 临时文档和未确认候选不进入永久资料库、普通日志或 Git。

## Phase 0: Research and validation

1. 对候选 PDF 文本提取库、DOCX 段落/表格提取库和本地 OCR 引擎做最小脱敏夹具验证。
2. 记录每个方案对页码、表格、图像 PDF、异常文件、Windows 安装和许可证的结果。
3. 选择能满足 F002 验收条件且依赖最少的方案；若验证发现契约不足，先更新契约和示例再实现。

## Phase 1: Parser and task seams

1. 建立文档输入校验、哈希和短生命周期任务状态。
2. 建立统一 ParsedSegment 接口，分别接入 PDF、DOCX 和图像 PDF OCR。
3. 为损坏、加密、超限、空文档、OCR 不可用和超时建立稳定错误映射。
4. 补充不落盘、不出站和临时资源清理边界测试。

## Phase 2: Candidate preview

1. 从 ParsedSegment 生成规则优先的标准字段候选。
2. 为每个候选补齐来源、位置、证据、置信度、警告和确认状态。
3. 实现 `profile.import.preview` 路由，严格校验共享契约并保证预览不改变资料。
4. 对已有字段生成冲突信息，对不确定内容保留人工处理状态。

## Phase 3: Review and confirmed persistence

1. 实现短生命周期候选任务的接受、修改、拒绝、取消和过期处理。
2. 实现 `profile.import.confirm` 路由，复用 F001 的字段校验、敏感字段策略、幂等和 profile version 检查。
3. 确认只写入 accept/modify 的候选；reject、未处理、过期和冲突失败不写入。
4. 更新 Options Page 的文件选择、预览、来源/置信度展示、冲突确认和失败重试入口。

## Phase 4: Verification and documentation

1. 执行 F002 quickstart、契约验证、Python 测试、扩展测试、类型检查、Lint、构建和隐私审计。
2. 使用脱敏固定夹具验证 PDF、DOCX、图像 PDF、失败文件和临时清理。
3. 更新本地服务和扩展 README、Roadmap 和 F002 验收记录。
4. 完成 Converge/Analyze 和代码审查后创建 Pull Request。

## Planned file boundaries

- `apps/local-agent/src/resume_agent/parsing/`: 文件校验、PDF/DOCX/OCR 解析和 ParsedSegment。
- `apps/local-agent/src/resume_agent/imports/`: ImportTask、候选预览、确认和生命周期。
- `apps/local-agent/src/resume_agent/api/profile_routes.py`: 只增加导入路由适配，不把解析逻辑塞进路由。
- `apps/extension/src/options/`: 文件选择、候选预览、确认和冲突 UI。
- `apps/local-agent/tests/`、`apps/extension/tests/`、`tests/contracts/`、`tests/security/`: 脱敏夹具与回归测试。
- `packages/contracts/v0.1/`: 只有发现真实契约缺口时才修改，并同步示例和测试。
