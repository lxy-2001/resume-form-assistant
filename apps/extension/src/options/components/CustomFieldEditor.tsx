export type CustomFieldEditorType = "text" | "date" | "number" | "boolean" | "enum" | "multivalue";
export type CustomFieldEditorScope = "global" | "website" | "application";
export type CustomFieldEditorSensitivity = "normal" | "sensitive" | "highly_sensitive";

interface CustomFieldEditorProps {
  title?: string;
  submitLabel?: string;
  valueRequired?: boolean;
  label: string;
  type: CustomFieldEditorType;
  value: string;
  options: string;
  scope: CustomFieldEditorScope;
  scopeContext: string;
  sensitivity: CustomFieldEditorSensitivity;
  saving: boolean;
  error: string | null;
  onLabelChange: (value: string) => void;
  onTypeChange: (value: CustomFieldEditorType) => void;
  onValueChange: (value: string) => void;
  onOptionsChange: (value: string) => void;
  onScopeChange: (value: CustomFieldEditorScope) => void;
  onScopeContextChange: (value: string) => void;
  onSensitivityChange: (value: CustomFieldEditorSensitivity) => void;
  onSave: () => void;
  onCancel: () => void;
}

export function CustomFieldEditor({
  title = "新增自定义字段",
  submitLabel = "确认添加",
  valueRequired = true,
  label,
  type,
  value,
  options,
  scope,
  scopeContext,
  sensitivity,
  saving,
  error,
  onLabelChange,
  onTypeChange,
  onValueChange,
  onOptionsChange,
  onScopeChange,
  onScopeContextChange,
  onSensitivityChange,
  onSave,
  onCancel,
}: CustomFieldEditorProps) {
  return (
    <section aria-labelledby="custom-field-title">
      <h2 id="custom-field-title">{title}</h2>
      <label htmlFor="custom-field-label">字段名称
        <input id="custom-field-label" value={label} onChange={(event) => onLabelChange(event.target.value)} />
      </label>
      <label htmlFor="custom-field-type">字段类型
        <select id="custom-field-type" aria-label="字段类型" value={type} onChange={(event) => onTypeChange(event.target.value as CustomFieldEditorType)}>
          <option value="text">文本</option>
          <option value="date">日期</option>
          <option value="number">数字</option>
          <option value="boolean">布尔</option>
          <option value="enum">枚举</option>
          <option value="multivalue">多值</option>
        </select>
      </label>
      {type === "boolean" ? (
        <label htmlFor="custom-field-value">字段值
          <select id="custom-field-value" aria-label="字段值" value={value} onChange={(event) => onValueChange(event.target.value)} aria-required={valueRequired}>
            <option value="">请选择</option>
            <option value="true">是</option>
            <option value="false">否</option>
          </select>
        </label>
      ) : (
        <label htmlFor="custom-field-value">字段值
          <input id="custom-field-value" type={type === "number" ? "number" : "text"} value={value} onChange={(event) => onValueChange(event.target.value)} aria-required={valueRequired} />
        </label>
      )}
      {(type === "enum" || type === "multivalue") ? (
        <label htmlFor="custom-field-options">允许选项（逗号分隔）
          <input id="custom-field-options" value={options} onChange={(event) => onOptionsChange(event.target.value)} />
        </label>
      ) : null}
      <label htmlFor="custom-field-scope">使用范围
        <select id="custom-field-scope" aria-label="使用范围" value={scope} onChange={(event) => onScopeChange(event.target.value as CustomFieldEditorScope)}>
          <option value="global">全部资料</option>
          <option value="website">指定网站</option>
          <option value="application">指定申请</option>
        </select>
      </label>
      {scope !== "global" ? (
        <label htmlFor="custom-field-scope-context">范围标识
          <input id="custom-field-scope-context" value={scopeContext} onChange={(event) => onScopeContextChange(event.target.value)} />
        </label>
      ) : null}
      <label htmlFor="custom-field-sensitivity">敏感级别
        <select id="custom-field-sensitivity" aria-label="敏感级别" value={sensitivity} onChange={(event) => onSensitivityChange(event.target.value as CustomFieldEditorSensitivity)}>
          <option value="normal">普通</option>
          <option value="sensitive">敏感</option>
          <option value="highly_sensitive">高度敏感</option>
        </select>
      </label>
      <p>保存自定义字段前需要你的明确确认；保存后可在资料列表中继续编辑。</p>
      {error ? <p role="alert">{error}</p> : null}
      <button type="button" onClick={onSave} disabled={saving}>{saving ? "保存中…" : submitLabel}</button>
      <button type="button" onClick={onCancel} disabled={saving}>取消</button>
    </section>
  );
}
