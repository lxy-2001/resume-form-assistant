import { profileFieldKey, type ProfileField, type ProfileRecord, type RecordType } from "../profileClient";

interface RecordEditorProps {
  record: ProfileRecord;
  index: number;
  total: number;
  editing: boolean;
  saving: boolean;
  labelForType: (type: RecordType) => string;
  fieldForType: (type: RecordType) => { id: string; label: string };
  displayValue: (value: ProfileField["value"]) => string;
  onEdit: (record: ProfileRecord) => void;
  onChange: (recordId: string, fieldKey: string, value: ProfileField["value"]) => void;
  onMove: (index: number, direction: -1 | 1) => void;
  onDelete: (recordId: string) => void;
  onSave: () => void;
  onCancel: () => void;
}

function sourceLabel(kind: ProfileField["source"]["kind"]): string {
  return ({ manual: "手动", import: "导入", rule: "规则", agent: "Agent", user_correction: "用户纠正" } as Record<string, string>)[kind] ?? kind;
}

function control(field: ProfileField, value: string, inputId: string, onChange: (value: ProfileField["value"]) => void) {
  const common = { id: inputId, "aria-label": field.label };
  if (field.field_type === "boolean") return <select {...common} value={value} onChange={(event) => onChange(event.target.value === "true")}><option value="true">是</option><option value="false">否</option></select>;
  if (field.field_type === "enum") return <select {...common} value={value} onChange={(event) => onChange(event.target.value)}>{(field.options ?? []).map((option) => <option key={String(option.value)} value={String(option.value)}>{option.label}</option>)}</select>;
  const type = field.field_type === "number" ? "number" : field.field_type === "date" ? "date" : "text";
  return <input {...common} type={type} value={value} onChange={(event) => onChange(field.field_type === "number" ? (event.target.value === "" ? "" : Number(event.target.value)) : field.field_type === "multivalue" ? event.target.value.split(",").map((item) => item.trim()).filter(Boolean) : event.target.value)} />;
}

export function RecordEditor2({ record, index, total, editing, saving, labelForType, fieldForType, displayValue, onEdit, onChange, onMove, onDelete, onSave, onCancel }: RecordEditorProps) {
  const fallback = fieldForType(record.record_type);
  return <article data-record-id={record.record_id}>
    <h3>{labelForType(record.record_type)}</h3>
    {record.fields.length > 0 ? record.fields.map((field) => {
      const fieldKey = profileFieldKey(field);
      const controlId = `record-${record.record_id}-field-${encodeURIComponent(fieldKey)}`;
      return editing ? (
        <label key={fieldKey} htmlFor={controlId}>{field.label || (field.id === fallback.id ? fallback.label : field.id)}{control(field, displayValue(field.value), controlId, (value) => onChange(record.record_id, fieldKey, value))}</label>
      ) : <div key={fieldKey}><p><span>{field.label}:</span> <span>{displayValue(field.value)}</span></p><p>来源：{sourceLabel(field.source.kind)}</p><p>确认状态：{field.confirmed ? "已确认" : "未确认"}</p><p>敏感级别：{field.sensitivity === "normal" ? "普通" : field.sensitivity === "sensitive" ? "敏感" : "高度敏感"}</p><p>使用范围：{field.scope === "global" ? "全部资料" : field.scope === "website" ? `指定网站（${field.scope_context ?? ""}）` : `指定申请（${field.scope_context ?? ""}）`}</p><p>更新时间：{field.updated_at}</p></div>;
    }) : <p>暂无字段</p>}
    <button type="button" onClick={() => onEdit(record)}>编辑</button><button type="button" onClick={() => onMove(index, -1)} disabled={index === 0}>上移</button><button type="button" onClick={() => onMove(index, 1)} disabled={index === total - 1}>下移</button><button type="button" onClick={() => onDelete(record.record_id)}>删除</button>
    {editing ? <><button type="button" onClick={onSave} disabled={saving}>保存记录</button><button type="button" onClick={onCancel} disabled={saving}>取消编辑</button></> : null}
  </article>;
}
