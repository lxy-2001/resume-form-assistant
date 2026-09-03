import { useEffect, useState } from "react";

import type { ProfileClient, ProfileField, ProfileSnapshot } from "./profileClient";

interface ProfilePageProps {
  client: ProfileClient;
  profileId: string;
}

function displayValue(value: ProfileField["value"]): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "object") return Array.isArray(value) ? value.join(", ") : JSON.stringify(value);
  return String(value);
}

function editableValue(field: ProfileField, value: string): ProfileField["value"] {
  if (field.field_type === "number") {
    const number = Number(value);
    return Number.isFinite(number) ? number : value;
  }
  if (field.field_type === "boolean") return value === "true";
  if (field.field_type === "multivalue") return value.split(",").map((item) => item.trim()).filter(Boolean);
  return value;
}

export function ProfilePage({ client, profileId }: ProfilePageProps) {
  const [snapshot, setSnapshot] = useState<ProfileSnapshot | null>(null);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    client
      .read(profileId)
      .then((loaded) => {
        if (!active) return;
        setSnapshot(loaded);
        setDraft(Object.fromEntries(loaded.fields.map((field) => [field.id, displayValue(field.value)])));
      })
      .catch(() => active && setError("资料读取失败，请检查本地服务"))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [client, profileId]);

  if (loading) return <p role="status">正在加载资料…</p>;
  if (error && !snapshot) return <p role="alert">{error}</p>;
  if (!snapshot) return <p role="alert">资料不可用</p>;

  const save = async () => {
    const blank = snapshot.fields.find((field) => draft[field.id]?.trim() === "");
    if (blank) {
      setError(`${blank.label}不能为空`);
      setMessage(null);
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
        fields: snapshot.fields.map((field) => ({ ...field, value: editableValue(field, draft[field.id] ?? "") })),
      });
      setSnapshot(updated);
      setDraft(Object.fromEntries(updated.fields.map((field) => [field.id, displayValue(field.value)])));
      setMessage("资料已保存");
    } catch {
      setError("资料保存失败，请检查本地服务");
    } finally {
      setSaving(false);
    }
  };

  const cancel = () => {
    setDraft(Object.fromEntries(snapshot.fields.map((field) => [field.id, displayValue(field.value)])));
    setError(null);
    setMessage("已取消未保存的修改");
  };

  return (
    <main aria-labelledby="profile-title">
      <h1 id="profile-title">我的简历资料</h1>
      {snapshot.is_empty ? <p>暂无资料，请先添加资料。</p> : null}
      {snapshot.fields.map((field) => (
        <div key={field.id}>
          <label htmlFor={`profile-${field.id}`}>{field.label}</label>
          <input
            id={`profile-${field.id}`}
            type={field.field_type === "email" ? "email" : "text"}
            value={draft[field.id] ?? ""}
            onChange={(event) => setDraft((current) => ({ ...current, [field.id]: event.target.value }))}
          />
        </div>
      ))}
      {error ? <p role="alert">{error}</p> : null}
      {message ? <p role="status">{message}</p> : null}
      <button type="button" onClick={save} disabled={saving}>
        {saving ? "保存中…" : "保存"}
      </button>
      <button type="button" onClick={cancel} disabled={saving}>
        取消
      </button>
    </main>
  );
}
