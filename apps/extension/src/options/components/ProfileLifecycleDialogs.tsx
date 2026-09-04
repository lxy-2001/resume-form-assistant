import { useEffect, useState } from "react";

import type {
  FieldDefinition,
  ProfileDeleteSelection,
  ProfileExportSelection,
  ProfileField,
  ProfileFieldSelector,
  ProfileRecord,
} from "../profileClient";

interface ProfileLifecycleDialogsProps {
  action: "export" | "delete" | null;
  fields: ProfileField[];
  records: ProfileRecord[];
  definitions: FieldDefinition[];
  saving: boolean;
  error: string | null;
  onClose: () => void;
  onExport: (path: string, selection: ProfileExportSelection) => void;
  onDelete: (selection: ProfileDeleteSelection) => void;
}

function fieldOptionValue(field: ProfileField): string {
  return `field-value:${encodeURIComponent(JSON.stringify([
    field.id,
    field.scope,
    field.scope_context ?? null,
  ]))}`;
}

function scopeLabel(field: ProfileField): string {
  const labels = { global: "全局", website: "网站", application: "本次申请" };
  const label = labels[field.scope];
  return field.scope_context ? `${label}：${field.scope_context}` : label;
}

export function ProfileLifecycleDialogs({
  action,
  fields,
  records,
  definitions,
  saving,
  error,
  onClose,
  onExport,
  onDelete,
}: ProfileLifecycleDialogsProps) {
  const [exportPath, setExportPath] = useState("C:\\resume-profile-export.json");
  const [exportScope, setExportScope] = useState("all");
  const [deleteScope, setDeleteScope] = useState("all");
  const fieldSelectors = new Map<string, ProfileFieldSelector>(
    fields.map((field) => [
      fieldOptionValue(field),
      {
        id: field.id,
        scope: field.scope,
        ...(field.scope_context ? { scope_context: field.scope_context } : {}),
      },
    ]),
  );

  useEffect(() => {
    if (action === "delete") {
      setDeleteScope("all");
    }
  }, [action]);

  if (action === "export") {
    const selection: ProfileExportSelection = exportScope === "all"
      ? { all_profile_data: true }
      : { scopes: [exportScope as "global" | "website" | "application"] };
    return (
      <section role="dialog" aria-labelledby="profile-export-title" aria-modal="true">
        <h2 id="profile-export-title">导出资料</h2>
        <p>导出文件只保存到本地，不会自动上传；请自行保管导出文件。</p>
        <label htmlFor="profile-export-scope">导出范围</label>
        <select
          id="profile-export-scope"
          value={exportScope}
          onChange={(event) => setExportScope(event.target.value)}
          disabled={saving}
        >
          <option value="all">全部资料</option>
          <option value="global">全局字段</option>
          <option value="website">网站范围字段</option>
          <option value="application">申请范围字段</option>
        </select>
        <label htmlFor="profile-export-path">导出文件路径</label>
        <input
          id="profile-export-path"
          value={exportPath}
          onChange={(event) => setExportPath(event.target.value)}
          disabled={saving}
        />
        {error ? <p role="alert">{error}</p> : null}
        <button type="button" onClick={onClose} disabled={saving}>取消导出</button>
        <button
          type="button"
          onClick={() => onExport(exportPath, selection)}
          disabled={saving || !exportPath.trim()}
        >{saving ? "导出中…" : "确认导出"}</button>
      </section>
    );
  }

  if (action === "delete") {
    let selection: ProfileDeleteSelection;
    if (deleteScope === "all") {
      selection = { delete_all: true };
    } else if (deleteScope.startsWith("record:")) {
      selection = { record_ids: [deleteScope.slice("record:".length)] };
    } else if (deleteScope.startsWith("custom:")) {
      selection = {
        custom_field_definition_ids: [deleteScope.slice("custom:".length)],
      };
    } else {
      const fieldSelector = fieldSelectors.get(deleteScope);
      selection = fieldSelector
        ? { field_values: [fieldSelector] }
        : { field_ids: [deleteScope.slice("field:".length)] };
    }
    const recordLabel = (record: ProfileRecord) => {
      const labels: Record<string, string> = {
        education: "教育经历",
        work: "工作经历",
        internship: "实习经历",
        project: "项目经历",
      };
      return labels[record.record_type] ?? "经历";
    };
    return (
      <section role="dialog" aria-labelledby="profile-delete-title" aria-modal="true">
        <h2 id="profile-delete-title">删除资料</h2>
        <p>删除操作需要确认，且完成后不能从资料库撤销。</p>
        <label htmlFor="profile-delete-scope">删除范围</label>
        <select
          id="profile-delete-scope"
          value={deleteScope}
          onChange={(event) => setDeleteScope(event.target.value)}
          disabled={saving}
        >
          <option value="all">全部资料</option>
          {fields.map((field) => (
            <option key={fieldOptionValue(field)} value={fieldOptionValue(field)}>
              字段：{field.label}（{scopeLabel(field)}）
            </option>
          ))}
          {records.map((record) => (
            <option key={record.record_id} value={`record:${record.record_id}`}>
              {recordLabel(record)}：{record.record_id}
            </option>
          ))}
          {definitions.filter((definition) => definition.is_custom).map((definition) => (
            <option key={definition.id} value={`custom:${definition.id}`}>
              自定义字段：{definition.label}
            </option>
          ))}
        </select>
        {error ? <p role="alert">{error}</p> : null}
        <button type="button" onClick={onClose} disabled={saving}>取消删除</button>
        <button type="button" onClick={() => onDelete(selection)} disabled={saving}>
          {saving ? "删除中…" : "确认删除"}
        </button>
      </section>
    );
  }

  return null;
}
