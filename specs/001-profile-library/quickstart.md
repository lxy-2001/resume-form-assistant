# F001 Quickstart: 本地资料库验收

本指南验证 F001 的资料维护闭环，不需要真实简历、浏览器网站、云端账户或远程模型。

## Prerequisites

- Windows 11；
- Python 3.11 和 Node.js 运行环境；
- 仓库已包含上游共享契约 v0.1；
- 使用测试目录中的合成资料，不把真实个人资料复制到仓库。

## Start the local service

从 apps/local-agent 安装开发依赖并启动本机服务。服务只监听 loopback；实际启动命令由
pyproject.toml 和 README 在实现任务中固定。

确认启动检查满足：

1. 第一次启动在用户应用数据目录生成加密资料文件和 OS keyring 引用；
2. 未配置安全 keyring 时服务拒绝明文降级并给出恢复提示；
3. 日志中不出现资料值、密钥、完整导出内容或绝对隐私路径。

## Scenario A: basic profile (US1)

1. 打开 Options Page 的资料库页面；
2. 保存合成的姓名、邮箱和一条教育记录；
3. 重新加载页面和本地服务；
4. 读取资料，确认值、类型、来源、确认状态和更新时间保持一致；
5. 编辑邮箱后保存，确认其他字段没有变化；
6. 输入非法邮箱或日期，确认保存被拒绝且旧值仍在。

Expected result: US1 的所有验收场景通过，资料文件保持加密。

## Scenario B: repeated records and custom field (US2)

1. 新增第二条教育记录和一条项目记录；
2. 编辑或删除其中一条，确认其他记录不变；
3. 创建一个枚举型自定义字段并明确确认；
4. 尝试创建与标准字段冲突的字段，确认被拒绝；
5. 输入不在枚举集合中的值，确认被拒绝；
6. 取消一次自定义字段创建，确认没有永久字段。

Expected result: 记录有独立 ID、顺序和范围；自定义字段不会覆盖标准定义。

## Scenario C: privacy, export and deletion (US3)

1. 准备普通字段、敏感字段和自定义字段；
2. 查看详情，确认来源、敏感级别和确认状态可见；
3. 选择部分范围并确认导出，读取导出文件确认只包含所选内容；
4. 取消一次导出，确认没有文件或资料变化；
5. 确认删除一个字段，再确认删除全部资料；
6. 重新读取资料，确认删除结果；
7. 模拟 keyring 缺失、文件篡改和写入中断，确认旧快照保留且错误可理解。

Expected result: 没有个人资料出站请求；删除和恢复行为符合 data-model.md 与
contracts/profile-lifecycle.md。

## Automated checks

实现完成后在仓库根目录运行：

- Python 单元、集成和契约测试；
- Options Page 交互测试；
- F001 专用端到端测试；
- JSON Schema 校验、脱敏/秘密扫描和网络出站拦截测试。

完成条件是所有测试通过，且每个 spec.md 功能需求至少有一个自动化场景或明确的
人工验收记录。
