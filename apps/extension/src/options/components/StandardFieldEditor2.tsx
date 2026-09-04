import type { FieldDefinition, FieldType } from "../profileClient";

type StandardFieldScope = "global" | "website" | "application";

interface StandardFieldEditorProps {
  definitions: FieldDefinition[];
  fieldId: string;
  value: string;
  scope: StandardFieldScope;
  scopeContext: string;
  saving: boolean;
  error: string | null;
  onFieldIdChange: (value: string) => void;
  onValueChange: (value: string) => void;
  onScopeChange: (value: StandardFieldScope) => void;
  onScopeContextChange: (value: string) => void;
  onSave: () => void;
  onCancel: () => void;
}

function inputType(fieldType: FieldType): string {
  if (fieldType === "email") return "email";
  if (fieldType === "number") return "number";
  if (fieldType === "date") return "date";
  return "text";
}

export function StandardFieldEditor2({
  definitions,
  fieldId,
  value,
  scope,
  scopeContext,
  saving,
  error,
  onFieldIdChange,
  onValueChange,
  onScopeChange,
  onScopeContextChange,
  onSave,
  onCancel,
}: StandardFieldEditorProps) {
  const selected = definitions.find((definition) => definition.id === fieldId);
  return (
    <section aria-labelledby="standard-field-title">
      <h2 id="standard-field-title">添加标准字段</h2>
      <label htmlFor="standard-field-id">标准字段
        <select id="standard-field-id" aria-label="标准字段" value={fieldId} onChange={(event) => onFieldIdChange(event.target.value)}>
          <option value="">请选择</option>
          {definitions.map((definition) => <option key={definition.id} value={definition.id}>{definition.label}</option>)}
        </select>
      </label>
      <label htmlFor="standard-field-value">字段值
        {selected?.field_type === "enum" ? (
          <select id="standard-field-value" aria-label="字段值" value={value} onChange={(event) => onValueChange(event.target.value)} disabled={!selected}>
            <option value="">请选择</option>
            {(selected.options ?? []).map((option) => <option key={String(option.value)} value={String(option.value)}>{option.label}</option>)}
          </select>
        ) : selected?.field_type === "boolean" ? (
          <select id="standard-field-value" aria-label="字段值" value={value} onChange={(event) => onValueChange(event.target.value)} disabled={!selected}>
            <option value="">请选择</option>
            <option value="true">是</option>
            <option value="false">否</option>
          </select>
        ) : (
          <input id="standard-field-value" type={inputType(selected?.field_type ?? "text")} value={value} onChange={(event) => onValueChange(event.target.value)} disabled={!selected} />
        )}
      </label>
      {selected?.field_type === "multivalue" ? <p>多值字段请用逗号分隔。</p> : null}
      {selected && selected.allowed_scopes.length > 1 ? (
        <label htmlFor="standard-field-scope">使用范围
          <select
            id="standard-field-scope"
            aria-label="使用范围"
            value={scope}
            onChange={(event) => onScopeChange(event.target.value as StandardFieldScope)}
          >
            {selected.allowed_scopes.map((allowedScope) => (
              <option key={allowedScope} value={allowedScope}>
                {allowedScope === "global" ? "全部资料" : allowedScope === "website" ? "指定网站" : "指定申请"}
              </option>
            ))}
          </select>
        </label>
      ) : null}
      {scope !== "global" ? (
        <label htmlFor="standard-field-scope-context">范围标识
          <input id="standard-field-scope-context" value={scopeContext} onChange={(event) => onScopeContextChange(event.target.value)} />
        </label>
      ) : null}
      {selected?.requires_confirmation ? <p>该字段保存前需要明确确认。</p> : null}
      {error ? <p role="alert">{error}</p> : null}
      <button type="button" onClick={onSave} disabled={saving || !selected}>{saving ? "保存中…" : "确认添加标准字段"}</button>
      <button type="button" onClick={onCancel} disabled={saving}>取消</button>
    </section>
  );
}
