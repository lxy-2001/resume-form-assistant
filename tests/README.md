# Tests

测试按模块和场景组织。跨扩展与本地服务的端到端测试放在 `tests/e2e/`。

共享契约的回归测试位于 `tests/contracts/`，校验
`packages/contracts/v0.1/contracts.schema.json` 及其脱敏示例，并锁定不自动提交、
明确用户确认和禁止可执行脚本等安全不变量。

运行契约测试：

```text
python -m pytest tests/contracts -q
```
