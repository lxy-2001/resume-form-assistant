# F003 Data Model: 资料标准化与人工纠正

## NormalizationTask

短生命周期任务，关联一个 F002 import task 和预览时的 F001 资料版本。

| 属性 | 约束 | 说明 |
| --- | --- | --- |
| task_id | 稳定、不透明、任务内唯一 | 由服务创建或复用请求提供 |
| source_task_id | 必填 | F002 任务标识；来源任务失效时本任务不能创建 |
| profile_id | 必填 | 目标资料库 |
| profile_version | 非负整数 | 预览时快照版本 |
| state | validating/ready/awaiting_review/confirming/completed/failed/cancelled/expired | 终态不可再次写入 |
| candidates | 0..n | 字段或重复记录候选 |
| issues | 0..n | 任务级和候选级问题 |
| model_used / remote_data_sent | 布尔 | F003 默认均为 false |
| created_at | 时间戳 | 用于任务 TTL |

## NormalizedCandidate

一个待确认的标准字段或记录建议。

| 属性 | 约束 | 说明 |
| --- | --- | --- |
| candidate_id | 任务内唯一 | 决定和回放的稳定键 |
| target_kind | field/record | 目标类型 |
| field_id | target_kind=field 时必填 | 标准或已确认自定义字段 |
| record_candidate_id | target_kind=record 时必填 | 指向任务内记录候选 |
| original_value | 可选但若存在必须脱敏展示 | F002 原始候选值 |
| normalized_value | 必填或显式缺失 | 规范化建议 |
| field_type / record_type | 与目标定义一致 | 记录类型仅允许 education/work/internship/project 或 unknown |
| source | 至少一个来源 | 文档、位置和 F002 候选标识 |
| confidence | 0..1 | 规则或适配器给出的解释性分数 |
| status | new/unchanged/possible_duplicate/conflict/unclassified/invalid | 用于 UI 分组 |
| requires_confirmation | 始终 true | F003 结果不自动写入 |
| issues | 0..n | 格式、冲突或人工操作提示 |

## RecordCandidate

教育、工作、实习或项目的任务内记录候选。包含 `record_candidate_id`、`record_type`、位置建议、字段候选列表、已有记录匹配候选和合并建议。未确认的记录不能伪装成 F001 的 `RepeatableRecord`。

## NormalizationDecision

用户对字段或记录候选作出的 `accept`、`modify`、`merge`、`skip` 或 `reject` 决定。`modify` 必须携带新值；`merge` 必须携带目标记录标识和字段级最终值；所有能产生持久化结果的决定必须带 `user_confirmed=true`。

## Invariants

1. 预览不改变 F001 快照、字段定义或版本号。
2. 每个候选始终要求用户确认；敏感字段、长文本、新增记录和冲突合并不能降低确认级别。
3. 每个候选至少关联一个 F002 来源或可验证的规则来源；否则只能是 `unclassified` 或 `invalid`。
4. 版本过期、任务过期、取消或拒绝时不得写入任何未确认结果。
5. 写入只能通过 F001 `ProfileService` 的原子 upsert，不能直接操作存储文件。
6. 普通日志不记录原始值、规范值、证据正文或完整本地路径。
