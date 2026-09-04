# F001 Data Model: 本地简历资料库

**Date**: 2026-09-03
**Source**: specs/001-profile-library/spec.md and packages/contracts/v0.1

## Modeling Principles

- 标准字段语义来自产品基线和共享契约；资料库不为每个网站复制一套字段。
- “定义”和“值”分离：标准字段定义由系统提供，自定义字段定义由用户确认后创建。
- 值必须带范围、来源、确认状态和更新时间；未填写不能伪装成默认值。
- 领域模型不包含网页 DOM、模型提示词或可执行脚本。

## Entities

### Profile

表示一个本地用户的一套主资料。

| 属性 | 约束 | 说明 |
| --- | --- | --- |
| profile_id | 稳定、不透明、必填 | 为未来多套资料保留区分能力 |
| schema_version | 必填 | 资料文档版本，用于迁移 |
| fields | 0..n | 标准或自定义字段值 |
| records | 0..n | 教育、工作、实习、项目等重复记录 |
| created_at / updated_at | 时间戳 | 资料集合生命周期 |

首版只创建一个主 Profile；不提供账户或云端身份。

### StandardFieldDefinition

系统预置字段的稳定语义定义。至少包含 field_id、显示名称、字段类型、默认敏感级别、允许范围和验证规则。定义由产品版本提供，用户只能使用，不能删除、改名或把自定义字段伪装成它。

标准字段集合以 product-brief-v1.md 为准，包含身份、联系方式、教育、经历、能力、成果、链接和常见申请答案类别。

### CustomFieldDefinition

用户确认创建的简单扩展字段。

| 属性 | 约束 |
| --- | --- |
| custom_field_id | 稳定且不与标准 field_id 冲突 |
| label | 非空、用户可读；与标准字段名称冲突时拒绝 |
| field_type | text/date/number/boolean/enum/multi_value |
| options | enum 或 multi_value 时非空且唯一 |
| scope | global/website/application |
| sensitivity | normal/sensitive/highly_sensitive |
| validation | 可选的长度、格式、范围限制 |
| created_at / updated_at | 时间戳 |

创建、修改定义和首次写入值都要求用户确认。

### FieldValue

某个字段在某个范围内的当前值。

| 属性 | 约束 |
| --- | --- |
| field_id | 指向标准或自定义字段定义 |
| value | 必须符合 field_type 和 validation |
| scope | global、website 或 application |
| scope_context | global 时为空；website/application 时必填 | 网站或本次申请上下文的不透明标识，不保存为模型可执行指令 |
| source | F001 为 manual；后续导入可扩展 |
| confirmed | F001 写入后为 true |
| sensitivity | 继承定义或显式提升，不得降低高风险级别 |
| updated_at | 每次成功写入更新 |

同一 field_id 在同一 scope 下只能有一个当前值。不同 scope 的值并存且必须显式展示，不能静默合并。

### RepeatableRecord

教育、工作、实习或项目的一条独立记录。

| 属性 | 约束 |
| --- | --- |
| record_id | 稳定、不透明 |
| record_type | education/work/internship/project |
| position | 用户可调整的展示顺序 |
| fields | 编辑中可为 0..n；确认保存后至少 1 个 |
| confirmed | 记录写入前必须确认 |
| created_at / updated_at | 时间戳 |

记录可以为空草稿，但取消编辑后不得保存空记录；删除记录不影响其他记录。

### ExportRequest（领域操作）

一次用户主动发起的导出操作。这里的领域对象不等同于线上的 `ProfileExportRequest`：请求字段以共享 Schema 为准，`export_id` 由服务在成功响应中生成。

| 属性 | 约束 |
| --- | --- |
| profile_id / expected_profile_version | 资料身份和读取一致性版本 |
| selected_scopes / selected_ids | 明确导出范围，对应请求的 `selection` |
| user_confirmed | 导出前必须为 true |
| destination | 用户选择的本地位置，不由服务上传 |
| result | 成功由响应的 `task_state=completed`、`status=written` 表示；失败使用 `ErrorResponse`；用户在请求发出前取消则不产生变更 |

导出文件包含经过选择的资料数据和必要的版本信息，不包含密钥；导出完成后不自动删除或上传原资料。

## Relationships

    Profile
    ├── 0..n StandardFieldValue ──> StandardFieldDefinition
    ├── 0..n CustomFieldValue ────> CustomFieldDefinition
    └── 0..n RepeatableRecord
          └── 0..n FieldValue（确认保存的记录为 1..n）
    ExportRequest ── selects ──> Profile / FieldValue / RepeatableRecord

## Value and State Rules

### Field lifecycle

    absent
      → draft
      → pending_confirmation
      → confirmed
      → replaced
      → deleted

- draft、pending_confirmation 不可被后续网页填写功能读取为已确认资料；
- replaced 保留在一次内存事务或审计摘要中即可，首版不要求历史版本界面；
- deleted 不再出现在正常读取结果中。

### Storage envelope lifecycle

    uninitialized → key_created → encrypted_snapshot
    encrypted_snapshot → new_encrypted_snapshot
    encrypted_snapshot → read_error / recovery_required

- keyring 丢失或解密认证失败时进入 recovery_required，不生成新密钥覆盖旧文件；
- 写入失败保留旧快照；
- 完整删除时先处理并验证加密快照，再处理 keyring 引用；任何一步失败都返回可区分的 partial-failure 并向用户报告，不伪造成功。

## Validation Invariants

1. 标准 field_id 不可被自定义定义占用。
2. sensitive 或 highly_sensitive 值必须 requires_confirmation=true；未确认值不可提交。
3. 日期、数字、枚举和多值遵循字段定义的类型与限制。
4. null、空字符串和缺失值的语义必须由字段类型明确区分；空状态不得自动生成默认值。
5. scope=website 时必须带 scope_context 网站范围；scope=application 时必须带 scope_context 本次申请上下文标识；global 不得带 scope_context。
6. 每次持久化快照必须通过完整结构校验和认证标签校验。
7. 资料、导出内容和密钥不能出现在普通日志。

## Mapping to Shared Contracts

F001 使用共享契约中的 ProfileField、FieldType、Scope、Sensitivity、Source、ValidationRule 和确认字段。写入、读取、导出和删除分别映射到已合并的 `ProfileUpsertRequest/Response`、`ProfileReadRequest/Response`、`ProfileExportRequest/Response` 和 `ProfileDeleteRequest/Response`。领域对象不直接暴露加密 envelope。
