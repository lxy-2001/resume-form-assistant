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

启动本地服务（已安装依赖后）：

```powershell
.venv\Scripts\python -m resume_agent.main
```

默认只监听 `http://127.0.0.1:8765`。开发扩展来源可使用内置的 Vite 来源；如果使用已打包
的 Chrome/Edge 扩展，必须通过 `RESUME_AGENT_ALLOWED_ORIGINS` 配置精确的
`chrome-extension://<extension-id>` 或 `edge-extension://<extension-id>` 来源。配置项以逗号
分隔，不允许通配符或首尾空格；服务不会因为配置错误而放宽来源限制。

## F002 文档导入

`POST /v0/profile/import/preview` 接收扩展传来的 PDF/DOCX 内容，默认只做本地解析；文本层
不足的 PDF 会尝试使用本机 Tesseract，未安装 OCR 引擎时返回 `OCR_UNAVAILABLE`。预览只保留
短生命周期任务中的候选，不写入资料库。`POST /v0/profile/import/confirm` 必须携带用户对
每个候选的确认决定和预览时的资料版本；只有确认后的字段才复用 F001 的版本校验写入。
远程模型默认关闭，F002 不上传文件或候选。

## 数据安全与恢复边界

- 资料快照使用加密 JSON 保存，密钥材料由操作系统 keyring 管理；服务不会降级为明文保存。
- keyring 引用丢失、文件损坏或认证失败时只返回恢复提示，不会猜测或重建资料。
- 删除全部资料会先删除加密快照，再清理密钥引用；删除操作不可撤销。
- 导出只写入用户明确选择的本地绝对路径，默认不覆盖已有文件，也不会上传或返回资料内容。
- 真实资料、API Key、导出文件和本地配置只放在用户数据目录，不应提交到 Git。
