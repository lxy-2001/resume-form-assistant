# Local Agent Service

本地服务模块。负责资料库、PDF/Word/OCR 解析、标准化、规则校验、模型 Provider 和当前任务编排。

计划的主要区域：`api/`、`orchestrator/`、`profile/`、`parsing/`、`normalization/`、`matching/`、`providers/`、`policy/`、`validation/`、`storage/`。

## 本地开发

```powershell
cd apps/local-agent
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
.venv\Scripts\python -m pytest -q
```

F001 的本地服务通过注入 `ProfileService` 的测试和契约边界验证；可运行的生产启动入口属于后续服务集成任务。

## 数据安全与恢复边界

- 资料快照使用加密 JSON 保存，密钥材料由操作系统 keyring 管理；服务不会降级为明文保存。
- keyring 引用丢失、文件损坏或认证失败时只返回恢复提示，不会猜测或重建资料。
- 删除全部资料会先删除加密快照，再清理密钥引用；删除操作不可撤销。
- 导出只写入用户明确选择的本地绝对路径，默认不覆盖已有文件，也不会上传或返回资料内容。
- 真实资料、API Key、导出文件和本地配置只放在用户数据目录，不应提交到 Git。
