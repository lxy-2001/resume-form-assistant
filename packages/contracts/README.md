# Shared Contracts

保存浏览器扩展和本地服务共用的字段、请求响应、错误和版本契约。这里是跨模块数据格式的唯一事实来源。

当前版本：[`v0.1`](v0.1/README.md)。主 Schema 位于
[`v0.1/contracts.schema.json`](v0.1/contracts.schema.json)，脱敏示例位于
`v0.1/examples/`，回归测试位于 `tests/contracts/`。

不要在扩展或本地 Agent 内另建一套字段语义；新增或变更跨模块消息时，先更新主
Schema、示例和测试，再更新具体实现。真实个人资料、API Key 和网站配置禁止进入本目录。
