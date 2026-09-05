# Tasks: 文档资料解析与确认导入

## Phase 0: Research and contracts

- [ ] T001 从最新 `main` 创建 `feat/F002-document-parsing` 分支，并保留当前 worktree 未跟踪文件不动。
- [x] T002 为 PDF、DOCX、图像 PDF 准备脱敏最小夹具和失败夹具清单（测试运行时生成最小夹具，不提交真实资料）。
- [x] T003 完成解析库/OCR 引擎小验证，记录页码、表格、OCR、异常文件、Windows 可用性和许可证结论。
- [x] T004 校验现有 `DocumentRef`、`ProfileImportPreview*` 和 `ImportDecision` 契约；已同步 Schema、示例和契约测试。

## Phase 1: Parser and task lifecycle

- [x] T005 先写文件类型、大小、哈希、路径边界和 `.doc` 拒绝测试。
- [x] T006 实现文档输入校验和任务级文档元数据生成。
- [x] T007 先写 ParsedSegment 的文本、位置、证据和方法测试。
- [x] T008 实现 PDF 文本层解析，覆盖页码和空文本判断。
- [x] T009 实现 DOCX 段落与表格解析。
- [x] T010 先写图像 PDF OCR 成功、禁用、不可用和失败测试。
- [x] T011 实现本地 OCR 适配和 `ocr_used` 结果记录。
- [x] T012 实现 ImportTask 状态、过期、取消和临时资源清理。
- [x] T013 补充损坏、加密、超限、超时、空文档和清理失败的稳定错误测试。

## Phase 2: Candidate preview

- [x] T014 先写邮箱、手机号、日期等确定格式候选测试。
- [x] T015 实现规则优先候选生成，并保留文档位置和证据。
- [x] T016 为未归类文本、敏感字段和低置信度候选生成警告与确认要求。
- [x] T017 先写 `profile.import.preview` 的成功、空候选、错误、无出站和不变更资料测试。
- [x] T018 实现导入预览路由和结构化错误映射。
- [x] T019 补充已有字段冲突的候选展示与版本快照测试。

## Phase 3: Review and persistence

- [x] T020 先写 accept、modify、reject、cancel、expired 和重复决定测试。
- [x] T021 实现候选决定服务，保证未确认候选不进入 ProfileStore。
- [x] T022 先写确认写入的类型、敏感字段、scope、幂等和 stale-version 测试。
- [x] T023 实现 `profile.import.confirm`，复用 F001 ProfileService 并返回实际写入/拒绝 ID。
- [x] T024 补充远程同意、最小数据范围和出站状态审计测试。
- [x] T025 先写 Options Page 文件选择、预览、来源、置信度、冲突和取消测试。
- [x] T026 实现 Options Page 导入预览和确认交互，失败时提供重试或人工录入入口。

## Phase 4: Verification and delivery

- [x] T027 更新本地服务和扩展 README 的导入、OCR、隐私和失败处理说明。
- [x] T028 运行 `specs/002-document-parsing/quickstart.md` 全部场景并记录结果。
- [x] T029 运行本地服务测试、扩展测试、类型检查、Lint、构建、契约和隐私审计。
- [ ] T030 执行 Converge/Analyze，修正规格、计划、任务与实现之间的遗漏。
- [ ] T031 完成代码审查准备并创建 GitHub Pull Request，更新 Roadmap 状态。
