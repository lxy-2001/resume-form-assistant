# 贡献指南

## 开发前

请先阅读根目录 `AGENTS.md`、`.specify/memory/constitution.md`、产品基线和当前 Feature 的规格。产品级范围变化先修改产品文档和 Roadmap。

## Feature 流程

每个 Feature 使用独立分支，例如 `feat/F001-profile-library`，并在 `specs/` 下维护 `spec.md`、`plan.md` 和 `tasks.md`。实现前先明确验收标准，开发时优先补充测试。

## 提交与合并

- 不直接向 `main` 推送；
- 有意义的开发节点单独提交；
- 提交前运行相关测试和质量检查；
- Feature 完成后创建 GitHub Pull Request；
- 验收、检查和审阅通过后再合并。

不要提交真实个人资料、API Key、网站登录信息或本地运行数据。
