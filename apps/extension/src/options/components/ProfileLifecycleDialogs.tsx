import { useState } from "react";

import type {
  ProfileDeleteSelection,
  ProfileExportSelection,
  ProfileField,
} from "../profileClient";

interface ProfileLifecycleDialogsProps {
  action: "export" | "delete" | null;
  fields: ProfileField[];
  saving: boolean;
  error: string | null;
  onClose: () => void;
  onExport: (path: string, selection: ProfileExportSelection) => void;
  onDelete: (selection: ProfileDeleteSelection) => void;
}

export function ProfileLifecycleDialogs({
  action,
  fields,
  saving,
  error,
  onClose,
  onExport,
  onDelete,
}: ProfileLifecycleDialogsProps) {
  const [exportPath, setExportPath] = useState("C:\\resume-profile-export.json");
  const [exportScope, setExportScope] = useState("all");
  const [deleteScope, setDeleteScope] = useState("all");

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
    const selection: ProfileDeleteSelection = deleteScope === "all"
      ? { delete_all: true }
      : { field_ids: [deleteScope.slice("field:".length)] };
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
            <option key={`${field.id}-${field.scope}-${field.scope_context ?? ""}`} value={`field:${field.id}`}>
              字段：{field.label}
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
