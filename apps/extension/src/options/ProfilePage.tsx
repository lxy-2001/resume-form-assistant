import { useEffect, useState } from "react";

import { profileFieldKey } from "./profileClient";
import type {
  ProfileDeleteSelection,
  ProfileExportSelection,
  ProfileClient,
  ProfileField,
  ProfileRecord,
  ProfileSnapshot,
  RecordType,
} from "./profileClient";
import { RecordEditor2 as RecordEditor } from "./components/RecordEditor2";
import { CustomFieldEditor } from "./components/CustomFieldEditor";
import { StandardFieldEditor2 as StandardFieldEditor } from "./components/StandardFieldEditor2";
import { ProfileLifecycleDialogs } from "./components/ProfileLifecycleDialogs";
import { ProfileMetadata } from "./components/ProfileMetadata";

interface ProfilePageProps {
  client: ProfileClient;
  profileId: string;
}

type CustomFieldType = "text" | "date" | "number" | "boolean" | "enum" | "multivalue";
type CustomScope = "global" | "website" | "application";
type CustomSensitivity = "normal" | "sensitive" | "highly_sensitive";

function customFieldId(label: string): string {
  const slug = label.trim().toLowerCase().replace(/[^a-z0-9-]+/g, "-").replace(/^-+|-+$/g, "");
  const suffix = typeof crypto !== "undefined" && typeof crypto.randomUUID === "function" ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  return `custom.${slug || "field"}-${suffix}`;
}

function parseCustomFieldValue(type: CustomFieldType, value: string): ProfileField["value"] {
  if (type === "number") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : value;
  }
  if (type === "boolean") return value === "true";
  if (type === "multivalue") return value.split(",").map((item) => item.trim()).filter(Boolean);
  return value.trim();
}

function parseStandardFieldValue(type: ProfileField["field_type"], value: string): ProfileField["value"] {
  if (type === "number") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : value.trim();
  }
  if (type === "boolean") return value === "true";
  if (type === "multivalue") return value.split(",").map((item) => item.trim()).filter(Boolean);
  return value.trim();
}

function displayValue(value: ProfileField["value"]): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "object") return Array.isArray(value) ? value.join(", ") : JSON.stringify(value);
  return String(value);
}

function editableValue(field: ProfileField, value: string): ProfileField["value"] | undefined {
  if (field.field_type === "number") {
    if (!value.trim()) return undefined;
    const number = Number(value);
    return Number.isFinite(number) ? number : undefined;
  }
  if (field.field_type === "boolean") {
    if (value === "true") return true;
    if (value === "false") return false;
    return undefined;
  }
  if (field.field_type === "multivalue") {
    const values = value.split(",").map((item) => item.trim()).filter(Boolean);
    return values.length > 0 ? values : undefined;
  }
  return value;
}

function recordLabel(type: RecordType): string {
  if (type === "education") return "教育经历";
  if (type === "project") return "项目经历";
  if (type === "internship") return "实习经历";
  return "工作经历";
}

function recordField(type: RecordType): { id: string; label: string } {
  if (type === "education") return { id: "education.school_name", label: "院校/培养单位" };
  return { id: "experience.organization", label: "公司/单位/组织" };
}

function newRecordId(type: RecordType): string {
  const suffix = typeof crypto !== "undefined" && typeof crypto.randomUUID === "function" ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  return `${type}-${suffix}`;
}

function makeRecord(type: RecordType): ProfileRecord {
  const now = new Date().toISOString();
  const field = recordField(type);
  return {
    record_id: newRecordId(type),
    record_type: type,
    position: 0,
    fields: [{
      id: field.id,
      label: field.label,
      field_type: "text",
      value: "",
      scope: "global",
      sensitivity: "normal",
      requires_confirmation: false,
      confirmed: true,
      source: { kind: "manual" },
      updated_at: now,
    }],
    confirmed: true,
    created_at: now,
    updated_at: now,
  };
}

export function ProfilePage({ client, profileId }: ProfilePageProps) {
  const [snapshot, setSnapshot] = useState<ProfileSnapshot | null>(null);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [records, setRecords] = useState<ProfileRecord[]>([]);
  const [editingRecordId, setEditingRecordId] = useState<string | null>(null);
  const [customFieldOpen, setCustomFieldOpen] = useState(false);
  const [standardFieldOpen, setStandardFieldOpen] = useState(false);
  const [standardFieldId, setStandardFieldId] = useState("");
  const [standardFieldValue, setStandardFieldValue] = useState("");
  const [standardFieldScopeContext, setStandardFieldScopeContext] = useState("");
  const [customFieldLabel, setCustomFieldLabel] = useState("");
  const [customFieldType, setCustomFieldType] = useState<CustomFieldType>("text");
  const [customFieldValue, setCustomFieldValue] = useState("");
  const [customFieldOptions, setCustomFieldOptions] = useState("");
  const [customFieldScope, setCustomFieldScope] = useState<CustomScope>("global");
  const [customFieldScopeContext, setCustomFieldScopeContext] = useState("");
  const [customFieldSensitivity, setCustomFieldSensitivity] = useState<CustomSensitivity>("normal");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lifecycleAction, setLifecycleAction] = useState<"export" | "delete" | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    client
      .read(profileId)
      .then((loaded) => {
        if (!active) return;
        setSnapshot(loaded);
        setRecords(loaded.records);
        setDraft(Object.fromEntries(loaded.fields.map((field) => [profileFieldKey(field), displayValue(field.value)])));
      })
      .catch(() => active && setError("资料读取失败，请检查本地服务"))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [client, profileId]);

  if (loading && !snapshot) return <>
    <p role="status">正在加载资料…</p>
    <button type="button" onClick={() => setCustomFieldOpen(true)}>新增自定义字段</button>
  </>;
  if (error && !snapshot) return <p role="alert">{error}</p>;
  if (!snapshot) return <p role="alert">资料不可用</p>;

  const save = async () => {
    const preparedFields: ProfileField[] = [];
    for (const field of snapshot.fields) {
      const raw = draft[profileFieldKey(field)] ?? "";
      if (!raw.trim()) {
        setError(`${field.label}不能为空`);
        setMessage(null);
        return;
      }
      const value = editableValue(field, raw);
      if (value === undefined) {
        setError(`${field.label}格式不正确`);
        setMessage(null);
        return;
      }
      preparedFields.push({ ...field, value });
    }
    setSaving(true);
    setError(null);
    try {
      const updated = await client.upsert({
        profile_id: profileId,
        expected_profile_version: snapshot.profile_version,
        user_confirmed: true,
        mode: "merge",
        fields: preparedFields,
      });
      setSnapshot(updated);
      setRecords(updated.records);
      setDraft(Object.fromEntries(updated.fields.map((field) => [profileFieldKey(field), displayValue(field.value)])));
      setMessage("资料已保存");
    } catch {
      setError("资料保存失败，请检查本地服务");
    } finally {
      setSaving(false);
    }
  };

  const saveRecord = async () => {
    if (!editingRecordId) return;
    const record = records.find((item) => item.record_id === editingRecordId);
    if (!record) return;
    if (record.fields.some((field) => displayValue(field.value).trim() === "")) {
      setError("经历至少需要填写一个字段");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const updated = await client.upsert({
        profile_id: profileId,
        expected_profile_version: snapshot.profile_version,
        user_confirmed: true,
        mode: "merge",
        fields: [],
        records: [record],
      });
      setSnapshot(updated);
      setRecords(updated.records);
      setEditingRecordId(null);
      setMessage("经历已保存");
    } catch {
      setError("经历保存失败，请检查本地服务");
    } finally {
      setSaving(false);
    }
  };

  const addRecord = (type: RecordType) => {
    const record = makeRecord(type);
    record.position = records.length;
    setRecords((current) => [...current, record]);
    setEditingRecordId(record.record_id);
    setError(null);
  };

  const editRecord = (record: ProfileRecord) => setEditingRecordId(record.record_id);

  const cancelRecordEdit = (recordId: string) => {
    const persisted = snapshot.records.find((record) => record.record_id === recordId);
    if (!persisted) {
      setRecords((current) => current.filter((record) => record.record_id !== recordId));
    } else {
      setRecords((current) => current.map((record) => record.record_id === recordId ? persisted : record));
    }
    setEditingRecordId(null);
    setError(null);
  };

  const updateRecordField = (recordId: string, fieldKey: string, value: ProfileField["value"]) => {
    setRecords((current) => current.map((record) => record.record_id !== recordId ? record : {
      ...record,
      fields: record.fields.map((field) => profileFieldKey(field) === fieldKey ? { ...field, value, updated_at: new Date().toISOString() } : field),
    }));
  };

  const moveRecord = async (index: number, direction: -1 | 1) => {
    const target = index + direction;
    if (target < 0 || target >= records.length) return;
    const previous = records;
    const reordered = [...records];
    [reordered[index], reordered[target]] = [reordered[target], reordered[index]];
    const normalized = reordered.map((record, position) => ({ ...record, position }));
    setRecords(normalized);
    setSaving(true);
    setError(null);
    try {
      const updated = await client.upsert({
        profile_id: profileId,
        expected_profile_version: snapshot.profile_version,
        user_confirmed: true,
        mode: "merge",
        fields: [],
        record_order: normalized.map((record) => record.record_id),
      });
      setSnapshot(updated);
      setRecords(updated.records);
    } catch {
      setRecords(previous);
      setError("经历排序失败，请检查本地服务");
    } finally {
      setSaving(false);
    }
  };

  const deleteRecord = async (recordId: string) => {
    if (!window.confirm("确认删除这条经历吗？")) return;
    setSaving(true);
    try {
      const updated = await client.upsert({
        profile_id: profileId,
        expected_profile_version: snapshot.profile_version,
        user_confirmed: true,
        mode: "merge",
        fields: [],
        delete_record_ids: [recordId],
      });
      setSnapshot(updated);
      setRecords(updated.records);
      setMessage("经历已删除");
    } catch {
      setError("经历删除失败，请检查本地服务");
    } finally {
      setSaving(false);
    }
  };

  const availableStandardDefinitions = snapshot.field_definitions.filter((definition) =>
    !definition.is_custom && !snapshot.fields.some((field) => field.id === definition.id),
  );
  const resetStandardFieldForm = () => {
    setStandardFieldOpen(false);
    setStandardFieldId("");
    setStandardFieldValue("");
    setStandardFieldScopeContext("");
  };
  const saveStandardField = async () => {
    const definition = availableStandardDefinitions.find((item) => item.id === standardFieldId);
    if (!definition) {
      setError("请选择标准字段");
      return;
    }
    if (!standardFieldValue.trim()) {
      setError(`${definition.label}不能为空`);
      return;
    }
    const scope = definition.allowed_scopes[0] ?? "global";
    if (scope !== "global" && !standardFieldScopeContext.trim()) {
      setError("网站或申请范围需要填写范围标识");
      return;
    }
    const now = new Date().toISOString();
    const field: ProfileField = {
      id: definition.id,
      label: definition.label,
      field_type: definition.field_type,
      value: parseStandardFieldValue(definition.field_type, standardFieldValue),
      scope,
      ...(scope !== "global" ? { scope_context: standardFieldScopeContext.trim() } : {}),
      sensitivity: definition.default_sensitivity,
      requires_confirmation: definition.requires_confirmation,
      confirmed: true,
      source: { kind: "manual" },
      updated_at: now,
      ...(definition.options ? { options: definition.options } : {}),
    };
    setSaving(true);
    setError(null);
    try {
      const updated = await client.upsert({
        profile_id: profileId,
        expected_profile_version: snapshot.profile_version,
        user_confirmed: true,
        mode: "merge",
        fields: [field],
      });
      setSnapshot(updated);
      setRecords(updated.records);
      setDraft(Object.fromEntries(updated.fields.map((item) => [profileFieldKey(item), displayValue(item.value)])));
      resetStandardFieldForm();
      setMessage("标准字段已保存");
    } catch {
      setError("标准字段保存失败，请检查本地服务");
    } finally {
      setSaving(false);
    }
  };

  const resetCustomFieldForm = () => {
    setCustomFieldOpen(false);
    setCustomFieldLabel("");
    setCustomFieldValue("");
    setCustomFieldOptions("");
    setCustomFieldType("text");
    setCustomFieldScope("global");
    setCustomFieldScopeContext("");
    setCustomFieldSensitivity("normal");
  };

  const saveCustomField = async () => {
    const label = customFieldLabel.trim();
    if (!label) {
      setError("字段名称不能为空");
      return;
    }
    const optionValues = customFieldOptions.split(",").map((item) => item.trim()).filter(Boolean);
    if ((customFieldType === "enum" || customFieldType === "multivalue") && optionValues.length === 0) {
      setError("枚举或多值字段至少需要一个选项");
      return;
    }
    if (new Set(optionValues).size !== optionValues.length) {
      setError("字段选项不能重复");
      return;
    }
    if (!customFieldValue.trim() && customFieldType !== "boolean") {
      setError("字段值不能为空");
      return;
    }
    if (customFieldScope !== "global" && !customFieldScopeContext.trim()) {
      setError("网站或申请范围需要填写范围标识");
      return;
    }
    const value = parseCustomFieldValue(customFieldType, customFieldValue);
    if (customFieldType === "enum" && !optionValues.includes(String(value))) {
      setError("字段值必须来自允许选项");
      return;
    }
    if (customFieldType === "multivalue" && (value as string[]).some((item) => !optionValues.includes(item))) {
      setError("多值字段中的每一项都必须来自允许选项");
      return;
    }
    if (customFieldType === "number" && typeof value !== "number") {
      setError("数字字段格式不正确");
      return;
    }
    const id = customFieldId(label);
    const now = new Date().toISOString();
    const options = optionValues.map((item) => ({ value: item, label: item }));
    const definition = {
      id,
      label,
      field_type: customFieldType,
      default_sensitivity: customFieldSensitivity,
      requires_confirmation: true,
      is_custom: true as const,
      allowed_scopes: [customFieldScope],
      ...(options.length > 0 ? { options } : {}),
      created_at: now,
      updated_at: now,
    };
    const field: ProfileField = {
      id,
      label,
      field_type: customFieldType,
      value,
      scope: customFieldScope,
      ...(customFieldScope !== "global" ? { scope_context: customFieldScopeContext.trim() } : {}),
      sensitivity: customFieldSensitivity,
      requires_confirmation: true,
      confirmed: true,
      source: { kind: "manual" },
      updated_at: now,
      is_custom: true,
      ...(options.length > 0 ? { options } : {}),
    };
    setSaving(true);
    setError(null);
    try {
      const updated = await client.upsert({
        profile_id: profileId,
        expected_profile_version: snapshot.profile_version,
        user_confirmed: true,
        mode: "merge",
        fields: [field],
        custom_field_definitions: [definition],
      });
      setSnapshot(updated);
      setRecords(updated.records);
      setDraft(Object.fromEntries(updated.fields.map((item) => [profileFieldKey(item), displayValue(item.value)])));
      resetCustomFieldForm();
      setMessage("自定义字段已保存");
    } catch {
      setError("自定义字段保存失败，请检查名称或选项");
    } finally {
      setSaving(false);
    }
  };
  const cancel = () => {
    setDraft(Object.fromEntries(snapshot.fields.map((field) => [profileFieldKey(field), displayValue(field.value)])));
    setError(null);
    setMessage("已取消未保存的修改");
  };
  const exportProfile = async (path: string, selection: ProfileExportSelection) => {
    if (!client.export) {
      setError("当前客户端不支持导出");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const result = await client.export({
        profile_id: profileId,
        expected_profile_version: snapshot.profile_version,
        user_confirmed: true,
        selection,
        format: "json",
        destination: {
          kind: "local_file",
          path,
          overwrite_existing: false,
        },
      });
      setLifecycleAction(null);
      setMessage(`资料已导出：${result.destination_display_name}`);
    } catch {
      setError("导出失败，请检查文件路径或本地服务");
    } finally {
      setSaving(false);
    }
  };

  const deleteProfile = async (selection: ProfileDeleteSelection) => {
    if (!client.delete) {
      setError("当前客户端不支持删除");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const result = await client.delete({
        profile_id: profileId,
        expected_profile_version: snapshot.profile_version,
        user_confirmed: true,
        selection,
      });
      const refreshed = await client.read(profileId);
      setSnapshot(refreshed);
      setRecords(refreshed.records);
      setDraft(Object.fromEntries(refreshed.fields.map((field) => [profileFieldKey(field), displayValue(field.value)])));
      setLifecycleAction(null);
      setMessage(result.all_data_deleted ? "资料已全部删除" : "所选资料已删除");
    } catch {
      setError("删除失败，请检查本地服务");
    } finally {
      setSaving(false);
    }
  };

  return (
    <main aria-labelledby="profile-title">
      <h1 id="profile-title">我的简历资料</h1>
      <ProfileMetadata snapshot={snapshot} />
      {snapshot.is_empty && records.length === 0 ? <p>暂无资料，请先添加资料。</p> : null}
      {standardFieldOpen ? (
        <StandardFieldEditor
          definitions={availableStandardDefinitions}
          fieldId={standardFieldId}
          value={standardFieldValue}
          scopeContext={standardFieldScopeContext}
          saving={saving}
          error={error}
          onFieldIdChange={setStandardFieldId}
          onValueChange={setStandardFieldValue}
          onScopeContextChange={setStandardFieldScopeContext}
          onSave={saveStandardField}
          onCancel={resetStandardFieldForm}
        />
      ) : (
        <button
          type="button"
          onClick={() => setStandardFieldOpen(true)}
          disabled={availableStandardDefinitions.length === 0}
        >添加标准字段</button>
      )}
      {snapshot.fields.map((field) => {
        const fieldKey = profileFieldKey(field);
        const controlId = `profile-${encodeURIComponent(fieldKey)}`;
        return (
          <div key={fieldKey}>
            <label htmlFor={controlId}>{field.label}</label>
            <input
              id={controlId}
              type={field.field_type === "email" ? "email" : "text"}
              value={draft[fieldKey] ?? ""}
              onChange={(event) => setDraft((current) => ({ ...current, [fieldKey]: event.target.value }))}
            />
            <p>来源：{field.source.kind === "manual" ? "手动" : field.source.kind}</p>
            <p>确认状态：{field.confirmed ? "已确认" : "未确认"}</p>
            <p>敏感级别：{field.sensitivity === "normal" ? "普通" : field.sensitivity === "sensitive" ? "敏感" : "高度敏感"}</p>
            <p>使用范围：{field.scope === "global" ? "全部资料" : field.scope === "website" ? `指定网站（${field.scope_context ?? ""}）` : `指定申请（${field.scope_context ?? ""}）`}</p>
            <p>更新时间：{field.updated_at}</p>
          </div>
        );
      })}

      <section aria-labelledby="records-title">
        <h2 id="records-title">重复经历</h2>
        <button type="button" onClick={() => addRecord("education")}>新增教育经历</button>
        <button type="button" onClick={() => addRecord("work")}>新增工作经历</button>
        <button type="button" onClick={() => addRecord("internship")}>新增实习经历</button>
        <button type="button" onClick={() => addRecord("project")}>新增项目经历</button>
        {records.map((record, index) => (
          <RecordEditor
            key={record.record_id}
            record={record}
            index={index}
            total={records.length}
            editing={editingRecordId === record.record_id}
            saving={saving}
            labelForType={recordLabel}
            fieldForType={recordField}
            displayValue={displayValue}
            onEdit={editRecord}
            onChange={updateRecordField}
            onMove={moveRecord}
            onDelete={deleteRecord}
            onSave={saveRecord}
            onCancel={() => cancelRecordEdit(record.record_id)}
          />
        ))}
      </section>

      <div>
        <button type="button" onClick={() => { setError(null); setLifecycleAction("export"); }} disabled={saving}>导出资料</button>
        <button type="button" onClick={() => { setError(null); setLifecycleAction("delete"); }} disabled={saving}>删除资料</button>
      </div>
      {customFieldOpen ? (
        <CustomFieldEditor
          label={customFieldLabel}
          type={customFieldType}
          value={customFieldValue}
          options={customFieldOptions}
          scope={customFieldScope}
          scopeContext={customFieldScopeContext}
          sensitivity={customFieldSensitivity}
          saving={saving}
          error={error}
          onLabelChange={setCustomFieldLabel}
          onTypeChange={setCustomFieldType}
          onValueChange={setCustomFieldValue}
          onOptionsChange={setCustomFieldOptions}
          onScopeChange={setCustomFieldScope}
          onScopeContextChange={setCustomFieldScopeContext}
          onSensitivityChange={setCustomFieldSensitivity}
          onSave={saveCustomField}
          onCancel={resetCustomFieldForm}
        />
      ) : <>
        <button type="button" onClick={() => setCustomFieldOpen(true)}>新增自定义字段</button>
        {error && !lifecycleAction ? <p role="alert">{error}</p> : null}
        {message ? <p role="status">{message}</p> : null}
        <button type="button" onClick={save} disabled={saving}>{saving ? "保存中…" : "保存"}</button>
        <button type="button" onClick={cancel} disabled={saving}>取消</button>
      </>}
      <ProfileLifecycleDialogs
        action={lifecycleAction}
        fields={snapshot.fields}
        saving={saving}
        error={error}
        onClose={() => { setLifecycleAction(null); setError(null); }}
        onExport={exportProfile}
        onDelete={deleteProfile}
      />
    </main>
  );
}
