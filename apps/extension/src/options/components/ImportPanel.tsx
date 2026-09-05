import { useState } from "react";
import type { ImportCandidate, ProfileClient, ProfileSnapshot } from "../profileClient";

interface ImportPanelProps {
  client: ProfileClient;
  profileId: string;
  snapshot: ProfileSnapshot;
  saving: boolean;
  onComplete: (profileVersion?: number) => void;
  onError: (message: string) => void;
}

export function ImportPanel({ client, profileId, snapshot, saving, onComplete, onError }: ImportPanelProps) {
  const [candidates, setCandidates] = useState<ImportCandidate[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const preview = async () => {
    if (!file || !client.importPreview) return;
    setBusy(true); setMessage(null);
    try {
      const result = await client.importPreview(file);
      setCandidates(result.candidates);
      setTaskId(result.task_id ?? result.document_id);
      setMessage(result.ocr_used ? "已完成本地 OCR，请逐项确认" : "已完成解析，请逐项确认");
    } catch (error) {
      onError(error instanceof Error ? error.message : "文档解析失败");
    } finally { setBusy(false); }
  };

  const decide = (candidateId: string, decision: "accept" | "reject") => {
    setCandidates((items) => items.map((item) => item.candidate_id === candidateId ? { ...item, _decision: decision } as ImportCandidate : item));
  };

  const confirm = async () => {
    if (!client.importConfirm || !taskId) return;
    setBusy(true); setMessage(null);
    try {
      const result = await client.importConfirm({
        task_id: taskId,
        profile_id: profileId,
        expected_profile_version: snapshot.profile_version,
        decisions: candidates.map((candidate) => ({
          candidate_id: candidate.candidate_id,
          decision: ((candidate as ImportCandidate & { _decision?: "accept" | "reject" })._decision ?? "reject"),
          user_confirmed: true,
        })),
      });
      setCandidates([]); setTaskId(null); setFile(null);
      setMessage(`已写入 ${result.written_field_ids.length} 个字段`);
      onComplete(result.profile_version);
    } catch (error) {
      onError(error instanceof Error ? error.message : "导入确认失败");
    } finally { setBusy(false); }
  };

  const cancel = () => {
    setCandidates([]);
    setTaskId(null);
    setFile(null);
    setMessage("已取消导入");
  };

  if (!client.importPreview || !client.importConfirm) return null;
  return (
    <section aria-labelledby="import-title">
      <h2 id="import-title">导入文档</h2>
      <input aria-label="选择 PDF 或 DOCX" type="file" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" onChange={(event) => setFile(event.target.files?.[0] ?? null)} disabled={busy || saving} />
      <button type="button" onClick={() => void preview()} disabled={!file || busy || saving}>解析预览</button>
      {message ? <p role="status">{message}</p> : null}
      {candidates.length > 0 ? <>
        <h3>待确认候选</h3>
        {candidates.map((candidate) => {
          const state = (candidate as ImportCandidate & { _decision?: "accept" | "reject" })._decision;
          return <article key={candidate.candidate_id}>
            <p><strong>{candidate.label}</strong>：{String(candidate.value)}</p>
            <p>来源：{candidate.source.location ?? candidate.source.document_ref ?? "文档"}；置信度：{Math.round(candidate.confidence * 100)}%</p>
            {candidate.existing_value_conflict ? <p role="alert">已有值：{String(candidate.existing_value)}，确认后才会替换</p> : null}
            <button type="button" onClick={() => decide(candidate.candidate_id, "accept")} aria-pressed={state === "accept"}>接受</button>
            <button type="button" onClick={() => decide(candidate.candidate_id, "reject")} aria-pressed={state === "reject"}>拒绝</button>
          </article>;
        })}
        <button type="button" onClick={cancel} disabled={busy || saving}>取消导入</button>
        <button type="button" onClick={() => void confirm()} disabled={busy || saving}>确认写入已接受字段</button>
      </> : null}
    </section>
  );
}
