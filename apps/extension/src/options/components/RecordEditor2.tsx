import { useState } from "react";

import {
  profileFieldKey,
  type FieldDefinition,
  type ProfileField,
  type ProfileRecord,
  type RecordType,
} from "../profileClient";

interface RecordEditorProps {
  record: ProfileRecord;
  index: number;
  total: number;
  definitions: FieldDefinition[];
  editing: boolean;
  saving: boolean;
  labelForType: (type: RecordType) => string;
  fieldForType: (type: RecordType) => { id: string; label: string };
  displayValue: (value: ProfileField["value"]) => string;
  onEdit: (record: ProfileRecord) => void;
  onChange: (recordId: string, fieldKey: string, value: ProfileField["value"]) => void;
  onAddField: (recordId: string, definitionId: string) => void;
  onMove: (index: number, direction: -1 | 1) => void;
  onDelete: (recordId: string) => void;
  onSave: () => void;
  onCancel: () => void;
}

function sourceLabel(kind: ProfileField["source"]["kind"]): string {
  return ({
    manual: "手动",
    import: "导入",
    rule: "规则",
    agent: "Agent",
    user_correction: "用户纠正",
  } as Record<string, string>)[kind] ?? kind;
}

function sensitivityLabel(value: ProfileField["sensitivity"]): string {
  return value === "normal" ? "普通" : value === "sensitive" ? "敏感" : "高度敏感";
}

function control(
  field: ProfileField,
  value: string,
  inputId: string,
  onChange: (value: ProfileField["value"]) => void,
) {
  const common = { id: inputId, "aria-label": field.label };
  if (field.field_type === "boolean") {
    return (
      <select
        {...common}
        value={value}
        onChange={(event) => onChange(event.target.value === "" ? "" : event.target.value === "true")}
      >
        <option value="">请选择</option>
        <option value="true">是</option>
        <option value="false">否</option>
      </select>
    );
  }
  if (field.field_type === "enum") {
    return (
      <select {...common} value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="">请选择</option>
        {(field.options ?? []).map((option) => (
          <option key={String(option.value)} value={String(option.value)}>{option.label}</option>
        ))}
      </select>
    );
  }
  if (field.field_type === "rich_text" || field.field_type === "object") {
    return <textarea {...common} rows={4} value={value} onChange={(event) => onChange(event.target.value)} />;
  }
  const type = field.field_type === "number"
    ? "number"
    : field.field_type === "date"
      ? "date"
      : field.field_type === "year"
        ? "number"
        : field.field_type === "email"
          ? "email"
          : field.field_type === "phone"
            ? "tel"
            : "text";
  return (
    <input
      {...common}
      type={type}
      value={value}
      onChange={(event) => onChange(
        field.field_type === "number"
          ? (event.target.value === "" ? "" : Number(event.target.value))
          : field.field_type === "year"
            ? (event.target.value === "" ? "" : Number(event.target.value))
          : field.field_type === "multivalue"
            ? event.target.value.split(",").map((item) => item.trim()).filter(Boolean)
            : event.target.value,
      )}
    />
  );
}

function isDefinitionRelevant(definition: FieldDefinition, recordType: RecordType): boolean {
  // The first version creates record values only in the global scope. Hide
  // definitions that cannot be represented here instead of offering a no-op.
  if (definition.is_custom) return definition.allowed_scopes.includes("global");
  if (!definition.allowed_scopes.includes("global")) return false;
  return recordType === "education"
    ? definition.id.startsWith("education.")
    : definition.id.startsWith("experience.");
}

export function RecordEditor2({
  record,
  index,
  total,
  definitions,
  editing,
  saving,
  labelForType,
  fieldForType,
  displayValue,
  onEdit,
  onChange,
  onAddField,
  onMove,
  onDelete,
  onSave,
  onCancel,
}: RecordEditorProps) {
  const [newFieldId, setNewFieldId] = useState("");
  const fallback = fieldForType(record.record_type);
  const availableDefinitions = definitions.filter(
    (definition) => isDefinitionRelevant(definition, record.record_type)
      && !record.fields.some((field) => field.id === definition.id),
  );

  return (
    <article data-record-id={record.record_id}>
      <h3>{labelForType(record.record_type)}</h3>
      {record.fields.length > 0 ? record.fields.map((field) => {
        const fieldKey = profileFieldKey(field);
        const controlId = `record-${record.record_id}-field-${encodeURIComponent(fieldKey)}`;
        return editing ? (
          <label key={fieldKey} htmlFor={controlId}>
            {field.label || (field.id === fallback.id ? fallback.label : field.id)}
            {control(field, displayValue(field.value), controlId, (value) => onChange(record.record_id, fieldKey, value))}
          </label>
        ) : (
          <div key={fieldKey}>
            <p><span>{field.label}:</span> <span>{displayValue(field.value)}</span></p>
            <p>来源：{sourceLabel(field.source.kind)}</p>
            <p>确认状态：{field.confirmed ? "已确认" : "未确认"}</p>
            <p>敏感级别：{sensitivityLabel(field.sensitivity)}</p>
            <p>使用范围：{field.scope === "global" ? "全部资料" : field.scope === "website" ? `指定网站（${field.scope_context ?? ""}）` : `指定申请（${field.scope_context ?? ""}）`}</p>
            <p>更新时间：{field.updated_at}</p>
            <p>字段类型：{field.field_type}{field.is_custom ? "（自定义）" : "（标准）"}</p>
          </div>
        );
      }) : <p>暂无字段</p>}
      {editing && availableDefinitions.length > 0 ? (
        <div>
          <label htmlFor={`record-${record.record_id}-new-field`}>新增经历字段
            <select
              id={`record-${record.record_id}-new-field`}
              aria-label="新增经历字段"
              value={newFieldId}
              onChange={(event) => setNewFieldId(event.target.value)}
            >
              <option value="">请选择</option>
              {availableDefinitions.map((definition) => (
                <option key={definition.id} value={definition.id}>{definition.label}</option>
              ))}
            </select>
          </label>
          <button
            type="button"
            onClick={() => {
              if (newFieldId) onAddField(record.record_id, newFieldId);
              setNewFieldId("");
            }}
            disabled={!newFieldId || saving}
          >添加经历字段</button>
        </div>
      ) : null}
      <button type="button" onClick={() => onEdit(record)}>编辑</button>
      <button type="button" onClick={() => onMove(index, -1)} disabled={index === 0 || saving}>上移</button>
      <button type="button" onClick={() => onMove(index, 1)} disabled={index === total - 1 || saving}>下移</button>
      <button type="button" onClick={() => onDelete(record.record_id)} disabled={saving}>删除</button>
      {editing ? <>
        <button type="button" onClick={onSave} disabled={saving}>保存记录</button>
        <button type="button" onClick={onCancel} disabled={saving}>取消编辑</button>
      </> : null}
    </article>
  );
}
