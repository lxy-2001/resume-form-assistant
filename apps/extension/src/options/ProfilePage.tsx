import { useEffect, useState, type ChangeEvent } from "react";

import { profileFieldKey, ProfileClientError, ProfileRefreshError } from "./profileClient";
import type {
  ProfileDeleteSelection,
  ProfileExportSelection,
  ProfileClient,
  ProfileField,
  ProfileRecord,
  ProfileSnapshot,
  FieldType,
  RecordType,
} from "./profileClient";
import { RecordEditor2 as RecordEditor } from "./components/RecordEditor2";
import { CustomFieldEditor } from "./components/CustomFieldEditor";
import { StandardFieldEditor2 as StandardFieldEditor } from "./components/StandardFieldEditor2";
import { ProfileLifecycleDialogs } from "./components/ProfileLifecycleDialogs";
import { ProfileMetadata } from "./components/ProfileMetadata";
import { ImportPanel } from "./components/ImportPanel";

interface ProfilePageProps {
  client: ProfileClient;
  profileId: string;
}

type CustomFieldType = "text" | "date" | "number" | "boolean" | "enum" | "multivalue";
type CustomScope = "global" | "website" | "application";
type CustomSensitivity = "normal" | "sensitive" | "highly_sensitive";
type MutationIdentity = { request_id: string; task_id: string };

type RetryAction =
  | { kind: "read" }
  | { kind: "save"; identity: MutationIdentity }
  | { kind: "record"; identity: MutationIdentity }
  | { kind: "move"; index: number; direction: -1 | 1; identity: MutationIdentity }
  | { kind: "delete-record"; recordId: string; identity: MutationIdentity }
  | { kind: "standard"; identity: MutationIdentity }
  | { kind: "custom"; identity: MutationIdentity }
  | { kind: "export"; path: string; selection: ProfileExportSelection; identity: MutationIdentity }
  | { kind: "delete"; selection: ProfileDeleteSelection; identity: MutationIdentity };

function newMutationIdentity(operation: string): MutationIdentity {
  const suffix = typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  return {
    request_id: `extension-ui-${operation}-${suffix}`,
    task_id: `extension-ui-task-${operation}-${suffix}`,
  };
}

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
  if (type === "year") {
    const parsed = Number(value);
    return Number.isInteger(parsed) && parsed >= 1000 && parsed <= 9999 ? parsed : value.trim();
  }
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

function mutationRefreshFailed(error: unknown): boolean {
  return error instanceof ProfileRefreshError
    || (typeof error === "object" && error !== null && "mutationCommitted" in error
      && (error as { mutationCommitted?: unknown }).mutationCommitted === true);
}

function clientFailureMessage(error: unknown, fallback: string): string {
  if (!(error instanceof ProfileClientError)) return fallback;
  switch (error.code) {
    case "STALE_PROFILE_VERSION":
      return "资料版本已变化，请先重新读取后再操作";
    case "CONFIRMATION_REQUIRED":
      return "需要明确确认后才能保存或执行此操作";
    case "INVALID_FIELD_VALUE":
      return "字段值不符合要求，请修改后重试";
    case "CUSTOM_FIELD_CONFLICT":
      return "自定义字段名称或定义冲突，请修改后重试";
    case "INVALID_PROFILE_SELECTION":
      return "所选资料已变化，请重新打开并选择范围";
    case "STORAGE_UNAVAILABLE":
    case "STORAGE_CORRUPT_OR_UNRECOVERABLE":
      return "本地资料暂不可用，请重试或按提示手动恢复";
    default:
      return fallback;
  }
}

function retryForFailure(error: unknown, action: RetryAction): RetryAction | null {
  if (error instanceof ProfileClientError) {
    if (error.code === "STALE_PROFILE_VERSION") return { kind: "read" };
    if (!error.retryable && !["STORAGE_UNAVAILABLE", "STORAGE_CORRUPT_OR_UNRECOVERABLE"].includes(error.code ?? "")) {
      return null;
    }
  }
  return action;
}

function fieldControl(
  field: ProfileField,
  value: string,
  controlId: string,
  onChange: (value: string) => void,
) {
  const common = {
    id: controlId,
    "aria-label": field.label,
    value,
    onChange: (event: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
      onChange(event.target.value),
  };
  if (field.field_type === "boolean") {
    return (
      <select {...common}>
        <option value="">请选择</option>
        <option value="true">是</option>
        <option value="false">否</option>
      </select>
    );
  }
  if (field.field_type === "year") {
    return <input {...common} type="number" />;
  }
  if (field.field_type === "enum") {
    return (
      <select {...common}>
        <option value="">请选择</option>
        {(field.options ?? []).map((option) => (
          <option key={String(option.value)} value={String(option.value)}>
            {option.label}
          </option>
        ))}
      </select>
    );
  }
  if (field.field_type === "rich_text" || field.field_type === "object") {
    return <textarea {...common} rows={4} />;
  }
  const inputType: Record<FieldType, string> = {
    text: "text",
    email: "email",
    phone: "tel",
    date: "date",
    year: "number",
    number: "number",
    boolean: "text",
    enum: "text",
    multivalue: "text",
    rich_text: "text",
    object: "text",
  };
  return <input {...common} type={inputType[field.field_type]} />;
}

function requiresExplicitConfirmation(fields: ProfileField[]): boolean {
  return fields.some(
    (field) => field.requires_confirmation || field.sensitivity !== "normal",
  );
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
  const [standardFieldScope, setStandardFieldScope] = useState<CustomScope>("global");
  const [standardFieldScopeContext, setStandardFieldScopeContext] = useState("");
  const [customFieldLabel, setCustomFieldLabel] = useState("");
  const [customFieldType, setCustomFieldType] = useState<CustomFieldType>("text");
  const [customFieldValue, setCustomFieldValue] = useState("");
  const [customFieldOptions, setCustomFieldOptions] = useState("");
  const [customFieldScope, setCustomFieldScope] = useState<CustomScope>("global");
  const [customFieldScopeContext, setCustomFieldScopeContext] = useState("");
  const [customFieldSensitivity, setCustomFieldSensitivity] = useState<CustomSensitivity>("normal");
  const [editingCustomFieldId, setEditingCustomFieldId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lifecycleAction, setLifecycleAction] = useState<"export" | "delete" | null>(null);
  const [readAttempt, setReadAttempt] = useState(0);
  const [retryAction, setRetryAction] = useState<RetryAction | null>(null);

  const retryRead = () => {
    setError(null);
    setRetryAction(null);
    setReadAttempt((attempt) => attempt + 1);
  };

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    client
      .read(profileId)
      .then((loaded) => {
        if (!active) return;
        setSnapshot(loaded);
        setRecords(loaded.records);
        setDraft(Object.fromEntries(loaded.fields.map((field) => [profileFieldKey(field), displayValue(field.value)])));
        setRetryAction(null);
      })
      .catch(() => {
        if (!active) return;
        setError("资料读取失败，请检查本地服务");
        setRetryAction({ kind: "read" });
      })
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [client, profileId, readAttempt]);

  if (loading && !snapshot) return <>
    <p role="status">正在加载资料…</p>
    <button type="button" onClick={() => setCustomFieldOpen(true)}>新增自定义字段</button>
  </>;
  if (error && !snapshot) return <>
    <p role="alert">{error}</p>
    <button type="button" onClick={retryRead}>重试读取</button>
  </>;
  if (!snapshot) return <p role="alert">资料不可用</p>;

  const save = async (identity = newMutationIdentity("upsert")) => {
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
    if (requiresExplicitConfirmation(preparedFields)) {
      const labels = preparedFields
        .filter((field) => field.requires_confirmation || field.sensitivity !== "normal")
        .map((field) => field.label)
        .join("、");
      if (!window.confirm(`以下字段属于敏感资料，确认保存：${labels}？`)) {
        setError("已取消敏感字段保存");
        setMessage(null);
        return;
      }
    }
    setSaving(true);
    setError(null);
    try {
      const updated = await client.upsert({
        ...identity,
        profile_id: profileId,
        expected_profile_version: snapshot.profile_version,
        user_confirmed: true,
        mode: "merge",
        fields: preparedFields,
      });
      setSnapshot(updated);
      setRecords(updated.records);
      setDraft(Object.fromEntries(updated.fields.map((field) => [profileFieldKey(field), displayValue(field.value)])));
      setRetryAction(null);
      setMessage("资料已保存");
    } catch (cause) {
      if (mutationRefreshFailed(cause)) {
        setError("资料已保存，但刷新失败，请重试读取");
        setRetryAction({ kind: "read" });
      } else {
        setError(clientFailureMessage(cause, "资料保存失败，请检查本地服务"));
        setRetryAction(retryForFailure(cause, { kind: "save", identity }));
      }
    } finally {
      setSaving(false);
    }
  };

  const saveRecord = async (identity = newMutationIdentity("upsert")) => {
    if (!editingRecordId) return;
    const record = records.find((item) => item.record_id === editingRecordId);
    if (!record) return;
    if (record.fields.some((field) => displayValue(field.value).trim() === "")) {
      setError("经历至少需要填写一个字段");
      return;
    }
    if (requiresExplicitConfirmation(record.fields)) {
      if (!window.confirm("这条经历包含敏感资料，确认保存吗？")) {
        setError("已取消敏感经历保存");
        return;
      }
    }
    setSaving(true);
    setError(null);
    try {
      const updated = await client.upsert({
        ...identity,
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
      setRetryAction(null);
      setMessage("经历已保存");
    } catch (cause) {
      if (mutationRefreshFailed(cause)) {
        setError("经历已保存，但刷新失败，请重试读取");
        setRetryAction({ kind: "read" });
      } else {
        setError(clientFailureMessage(cause, "经历保存失败，请检查本地服务"));
        setRetryAction(retryForFailure(cause, { kind: "record", identity }));
      }
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

  const addRecordField = (recordId: string, definitionId: string) => {
    const definition = snapshot.field_definitions.find((item) => item.id === definitionId);
    if (!definition || !definition.allowed_scopes.includes("global")) return;
    setRecords((current) => current.map((record) => {
      if (record.record_id !== recordId || record.fields.some((field) => field.id === definitionId)) {
        return record;
      }
      const now = new Date().toISOString();
      const emptyValue: ProfileField["value"] = definition.field_type === "multivalue" ? [] : "";
      const field: ProfileField = {
        id: definition.id,
        label: definition.label,
        field_type: definition.field_type,
        value: emptyValue,
        scope: "global",
        sensitivity: definition.default_sensitivity,
        requires_confirmation: definition.requires_confirmation,
        confirmed: true,
        source: { kind: "manual" },
        updated_at: now,
        is_custom: definition.is_custom,
        aliases: definition.aliases,
        options: definition.options,
        validation: definition.validation,
      };
      return { ...record, fields: [...record.fields, field], updated_at: now };
    }));
  };

  const moveRecord = async (
    index: number,
    direction: -1 | 1,
    identity = newMutationIdentity("upsert"),
  ) => {
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
        ...identity,
        profile_id: profileId,
        expected_profile_version: snapshot.profile_version,
        user_confirmed: true,
        mode: "merge",
        fields: [],
        record_order: normalized.map((record) => record.record_id),
      });
      setSnapshot(updated);
      setRecords(updated.records);
      setRetryAction(null);
    } catch (cause) {
      setRecords(previous);
      if (mutationRefreshFailed(cause)) {
        setError("排序已保存，但刷新失败，请重试读取");
        setRetryAction({ kind: "read" });
      } else {
        setError(clientFailureMessage(cause, "经历排序失败，请检查本地服务"));
        setRetryAction(retryForFailure(cause, { kind: "move", index, direction, identity }));
      }
    } finally {
      setSaving(false);
    }
  };

  const deleteRecord = async (
    recordId: string,
    identity = newMutationIdentity("upsert"),
  ) => {
    if (!window.confirm("确认删除这条经历吗？")) return;
    if (!snapshot.records.some((record) => record.record_id === recordId)) {
      setRecords((current) => current.filter((record) => record.record_id !== recordId));
      setEditingRecordId(null);
      setMessage("已取消新增经历");
      setError(null);
      return;
    }
    setSaving(true);
    try {
      const updated = await client.upsert({
        ...identity,
        profile_id: profileId,
        expected_profile_version: snapshot.profile_version,
        user_confirmed: true,
        mode: "merge",
        fields: [],
        delete_record_ids: [recordId],
      });
      setSnapshot(updated);
      setRecords(updated.records);
      setRetryAction(null);
      setMessage("经历已删除");
    } catch (cause) {
      if (mutationRefreshFailed(cause)) {
        setError("经历已删除，但刷新失败，请重试读取");
        setRetryAction({ kind: "read" });
      } else {
        setError(clientFailureMessage(cause, "经历删除失败，请检查本地服务"));
        setRetryAction(retryForFailure(cause, { kind: "delete-record", recordId, identity }));
      }
    } finally {
      setSaving(false);
    }
  };

  const availableStandardDefinitions = snapshot.field_definitions.filter((definition) =>
    !definition.is_custom && definition.allowed_scopes.some((scope) =>
      scope !== "global" || !snapshot.fields.some((field) => field.id === definition.id && field.scope === "global"),
    ),
  );
  const resetStandardFieldForm = () => {
    setStandardFieldOpen(false);
    setStandardFieldId("");
    setStandardFieldValue("");
    setStandardFieldScope("global");
    setStandardFieldScopeContext("");
  };
  const selectStandardField = (fieldId: string) => {
    setStandardFieldId(fieldId);
    const definition = availableStandardDefinitions.find((item) => item.id === fieldId);
    setStandardFieldScope((definition?.allowed_scopes[0] ?? "global") as CustomScope);
    setStandardFieldScopeContext("");
  };
  const saveStandardField = async (identity = newMutationIdentity("upsert")) => {
    const definition = availableStandardDefinitions.find((item) => item.id === standardFieldId);
    if (!definition) {
      setError("请选择标准字段");
      return;
    }
    if (!standardFieldValue.trim()) {
      setError(`${definition.label}不能为空`);
      return;
    }
    const scope = standardFieldScope;
    if (!definition.allowed_scopes.includes(scope)) {
      setError("所选字段不支持该使用范围");
      return;
    }
    if (scope !== "global" && !standardFieldScopeContext.trim()) {
      setError("网站或申请范围需要填写范围标识");
      return;
    }
    if (definition.requires_confirmation || definition.default_sensitivity !== "normal") {
      if (!window.confirm(`字段“${definition.label}”属于敏感资料，确认保存吗？`)) {
        setError("已取消敏感标准字段保存");
        setRetryAction(null);
        return;
      }
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
      ...(definition.aliases ? { aliases: definition.aliases } : {}),
      ...(definition.validation ? { validation: definition.validation } : {}),
    };
    if (definition.field_type === "year" && typeof field.value !== "number") {
      setError(`${definition.label}格式不正确`);
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const updated = await client.upsert({
        ...identity,
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
      setRetryAction(null);
      setMessage("标准字段已保存");
    } catch (cause) {
      if (mutationRefreshFailed(cause)) {
        setError("标准字段已保存，但刷新失败，请重试读取");
        setRetryAction({ kind: "read" });
      } else {
        setError(clientFailureMessage(cause, "标准字段保存失败，请检查本地服务"));
        setRetryAction(retryForFailure(cause, { kind: "standard", identity }));
      }
    } finally {
      setSaving(false);
    }
  };

  const resetCustomFieldForm = () => {
    setCustomFieldOpen(false);
    setEditingCustomFieldId(null);
    setCustomFieldLabel("");
    setCustomFieldValue("");
    setCustomFieldOptions("");
    setCustomFieldType("text");
    setCustomFieldScope("global");
    setCustomFieldScopeContext("");
    setCustomFieldSensitivity("normal");
  };

  const openCustomFieldEditor = (fieldId?: string, valueKey?: string) => {
    if (!fieldId) {
      resetCustomFieldForm();
      setCustomFieldOpen(true);
      return;
    }
    const definition = snapshot.field_definitions.find(
      (item) => item.id === fieldId && item.is_custom,
    );
    if (!definition) return;
    const field = valueKey
      ? snapshot.fields.find((item) => profileFieldKey(item) === valueKey)
      : snapshot.fields.find((item) => item.id === fieldId);
    setEditingCustomFieldId(fieldId);
    setCustomFieldLabel(definition.label);
    setCustomFieldType(definition.field_type as CustomFieldType);
    setCustomFieldValue(field ? displayValue(field.value) : "");
    setCustomFieldOptions(
      (definition.options ?? []).map((item) => String(item.value)).join(","),
    );
    setCustomFieldScope(
      (field?.scope ?? definition.allowed_scopes[0] ?? "global") as CustomScope,
    );
    setCustomFieldScopeContext(field?.scope_context ?? "");
    setCustomFieldSensitivity(
      (field?.sensitivity ?? definition.default_sensitivity) as CustomSensitivity,
    );
    setError(null);
    setCustomFieldOpen(true);
  };

  const saveCustomField = async (identity = newMutationIdentity("upsert")) => {
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
      setError(editingCustomFieldId ? "字段值不能为空；如需删除请使用删除资料" : "字段值不能为空");
      return;
    }
    if (
      customFieldType === "boolean"
      && !["true", "false"].includes(customFieldValue)
    ) {
      setError("布尔字段必须明确选择是或否");
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
    const id = editingCustomFieldId ?? customFieldId(label);
    const existingDefinition = editingCustomFieldId
      ? snapshot.field_definitions.find(
        (item) => item.id === editingCustomFieldId && item.is_custom,
      )
      : undefined;
    const now = new Date().toISOString();
    const options = (customFieldType === "enum" || customFieldType === "multivalue")
      ? optionValues.map((item) => ({ value: item, label: item }))
      : undefined;
    const definition = {
      id,
      label,
      field_type: customFieldType,
      default_sensitivity: customFieldSensitivity,
      requires_confirmation: true,
      is_custom: true as const,
      // Editing a value must not silently narrow a definition that already
      // supports other scopes. A newly selected scope may be added explicitly.
      allowed_scopes: Array.from(new Set([
        ...(existingDefinition?.allowed_scopes ?? []),
        customFieldScope,
      ])),
      ...(options && options.length > 0 ? { options } : {}),
      ...(existingDefinition?.aliases ? { aliases: existingDefinition.aliases } : {}),
      ...(existingDefinition?.validation ? { validation: existingDefinition.validation } : {}),
      ...(existingDefinition?.created_at
        ? { created_at: existingDefinition.created_at }
        : { created_at: now }),
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
      ...(options && options.length > 0 ? { options } : {}),
    };
    setSaving(true);
    setError(null);
    try {
      const updated = await client.upsert({
        ...identity,
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
      setRetryAction(null);
      setMessage(editingCustomFieldId ? "自定义字段定义已更新" : "自定义字段已保存");
    } catch (cause) {
      setError(
        editingCustomFieldId
          ? "自定义字段定义更新失败，请检查名称、类型或已有值"
          : "自定义字段保存失败，请检查名称或选项",
      );
      if (mutationRefreshFailed(cause)) {
        setError("自定义字段已保存，但刷新失败，请重试读取");
        setRetryAction({ kind: "read" });
      } else {
        setRetryAction(retryForFailure(cause, { kind: "custom", identity }));
      }
    } finally {
      setSaving(false);
    }
  };
  const cancel = () => {
    setDraft(Object.fromEntries(snapshot.fields.map((field) => [profileFieldKey(field), displayValue(field.value)])));
    setError(null);
    setMessage("已取消未保存的修改");
  };
  const exportProfile = async (
    path: string,
    selection: ProfileExportSelection,
    identity = newMutationIdentity("export"),
  ) => {
    if (!client.export) {
      setError("当前客户端不支持导出");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const result = await client.export({
        ...identity,
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
      setRetryAction(null);
      setMessage(`资料已导出：${result.destination_display_name}`);
    } catch (cause) {
      setError(clientFailureMessage(cause, "导出失败，请检查文件路径或本地服务"));
      setRetryAction(retryForFailure(cause, { kind: "export", path, selection, identity }));
    } finally {
      setSaving(false);
    }
  };

  const deleteProfile = async (
    selection: ProfileDeleteSelection,
    identity = newMutationIdentity("delete"),
  ) => {
    if (!client.delete) {
      setError("当前客户端不支持删除");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const result = await client.delete({
        ...identity,
        profile_id: profileId,
        expected_profile_version: snapshot.profile_version,
        user_confirmed: true,
        selection,
      });
      let refreshed: ProfileSnapshot;
      try {
        refreshed = await client.read(profileId);
      } catch {
        setError("删除已执行，但资料刷新失败，请重试读取");
        setRetryAction({ kind: "read" });
        return;
      }
      setSnapshot(refreshed);
      setRecords(refreshed.records);
      setDraft(Object.fromEntries(refreshed.fields.map((field) => [profileFieldKey(field), displayValue(field.value)])));
      const pending = result.cleanup_pending ?? [];
      if (result.task_state === "partial" || pending.length > 0) {
        const warning = result.warnings?.find((item) => item.message)?.message;
        setError(
          `删除未完全完成${pending.length > 0 ? `（待处理：${pending.join("、")}）` : ""}。${warning ?? "请重试或手动处理。"}`,
        );
        setMessage(null);
        return;
      }
      setLifecycleAction(null);
      setRetryAction(null);
      setMessage(result.all_data_deleted ? "资料已全部删除" : "所选资料已删除");
    } catch (cause) {
      setError(clientFailureMessage(cause, "删除失败，请检查本地服务"));
      setRetryAction(retryForFailure(cause, { kind: "delete", selection, identity }));
    } finally {
      setSaving(false);
    }
  };

  const runRetry = () => {
    const action = retryAction;
    if (!action) return;
    if (action.kind === "read") {
      retryRead();
    } else if (action.kind === "save") {
      void save(action.identity);
    } else if (action.kind === "record") {
      void saveRecord(action.identity);
    } else if (action.kind === "move") {
      void moveRecord(action.index, action.direction, action.identity);
    } else if (action.kind === "delete-record") {
      void deleteRecord(action.recordId, action.identity);
    } else if (action.kind === "standard") {
      void saveStandardField(action.identity);
    } else if (action.kind === "custom") {
      void saveCustomField(action.identity);
    } else if (action.kind === "export") {
      void exportProfile(action.path, action.selection, action.identity);
    } else {
      void deleteProfile(action.selection, action.identity);
    }
  };

  return (
    <main aria-labelledby="profile-title">
      <h1 id="profile-title">我的简历资料</h1>
      <ProfileMetadata snapshot={snapshot} />
      <ImportPanel
        client={client}
        profileId={profileId}
        snapshot={snapshot}
        saving={saving}
        onComplete={() => setReadAttempt((attempt) => attempt + 1)}
        onError={(message) => { setError(message); setMessage(null); }}
      />
      {snapshot.is_empty && records.length === 0 ? <p>暂无资料，请先添加资料。</p> : null}
      {standardFieldOpen ? (
        <StandardFieldEditor
          definitions={availableStandardDefinitions}
          fieldId={standardFieldId}
          value={standardFieldValue}
          scope={standardFieldScope}
          scopeContext={standardFieldScopeContext}
          saving={saving}
          error={error}
          onFieldIdChange={selectStandardField}
          onValueChange={setStandardFieldValue}
          onScopeChange={setStandardFieldScope}
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
            {fieldControl(
              field,
              draft[fieldKey] ?? "",
              controlId,
              (value) => setDraft((current) => ({ ...current, [fieldKey]: value })),
            )}
            <p>来源：{field.source.kind === "manual" ? "手动" : field.source.kind}</p>
            <p>确认状态：{field.confirmed ? "已确认" : "未确认"}</p>
            <p>敏感级别：{field.sensitivity === "normal" ? "普通" : field.sensitivity === "sensitive" ? "敏感" : "高度敏感"}</p>
            <p>使用范围：{field.scope === "global" ? "全部资料" : field.scope === "website" ? `指定网站（${field.scope_context ?? ""}）` : `指定申请（${field.scope_context ?? ""}）`}</p>
            <p>更新时间：{field.updated_at}</p>
            <p>字段类型：{field.field_type}{field.is_custom ? "（自定义）" : "（标准）"}</p>
            {field.is_custom ? (
               <button type="button" onClick={() => openCustomFieldEditor(field.id, fieldKey)}>编辑定义</button>
            ) : null}
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
            definitions={snapshot.field_definitions}
            editing={editingRecordId === record.record_id}
            saving={saving}
            labelForType={recordLabel}
            fieldForType={recordField}
            displayValue={displayValue}
            onEdit={editRecord}
            onChange={updateRecordField}
            onAddField={addRecordField}
            onMove={moveRecord}
            onDelete={deleteRecord}
            onSave={saveRecord}
            onCancel={() => cancelRecordEdit(record.record_id)}
          />
        ))}
      </section>

      <div>
        <button type="button" onClick={() => { setError(null); setRetryAction(null); setLifecycleAction("export"); }} disabled={saving}>导出资料</button>
        <button type="button" onClick={() => { setError(null); setRetryAction(null); setLifecycleAction("delete"); }} disabled={saving}>删除资料</button>
      </div>
      {customFieldOpen ? (
        <CustomFieldEditor
          title={editingCustomFieldId ? "编辑自定义字段定义" : "新增自定义字段"}
          submitLabel={editingCustomFieldId ? "确认更新" : "确认添加"}
          valueRequired
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
        {error && !lifecycleAction && !standardFieldOpen ? <p role="alert">{error}</p> : null}
        {message ? <p role="status">{message}</p> : null}
        <button type="button" onClick={() => void save()} disabled={saving}>{saving ? "保存中…" : "保存"}</button>
        <button type="button" onClick={cancel} disabled={saving}>取消</button>
      </>}
      <ProfileLifecycleDialogs
        action={lifecycleAction}
        fields={snapshot.fields}
        records={snapshot.records}
        definitions={snapshot.field_definitions}
        saving={saving}
        error={error}
        onClose={() => { setLifecycleAction(null); setError(null); }}
        onExport={exportProfile}
        onDelete={deleteProfile}
      />
      {error && retryAction ? (
        <button type="button" onClick={runRetry} disabled={saving}>
          {retryAction.kind === "read" ? "重试读取" : "重试"}
        </button>
      ) : null}
    </main>
  );
}
