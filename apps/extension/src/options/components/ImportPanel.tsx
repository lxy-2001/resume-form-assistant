import { useState } from "react";
import type { ImportCandidate, NormalizedCandidate, ProfileClient, ProfileSnapshot } from "../profileClient";

interface ImportPanelProps {
  client: ProfileClient;
  profileId: string;
  snapshot: ProfileSnapshot;
  saving: boolean;
  onComplete: (profileVersion?: number) => void;
  onError: (message: string) => void;
}

type Decision = "accept" | "modify" | "skip" | "reject";
type ReviewCandidate = ImportCandidate | NormalizedCandidate;

export function ImportPanel({ client, profileId, snapshot, saving, onComplete, onError }: ImportPanelProps) {
  const [candidates, setCandidates] = useState<ReviewCandidate[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [normalizationTaskId, setNormalizationTaskId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const preview = async () => {
    if (!file || !client.importPreview) return;
    setBusy(true); setMessage(null);
    try {
      const result = await client.importPreview(file);
      setTaskId(result.task_id ?? result.document_id);
      if (client.normalizationPreview && result.task_id) {
        const normalized = await client.normalizationPreview(result.task_id, profileId);
        setCandidates(normalized.candidates);
        setNormalizationTaskId(normalized.task_id);
      } else setCandidates(result.candidates);
      setMessage(result.ocr_used ? "已完成本地 OCR，请逐项确认" : "已完成解析和标准化，请逐项确认");
    } catch (error) { onError(error instanceof Error ? error.message : "文档解析失败"); }
    finally { setBusy(false); }
  };

  const candidateValue = (candidate: ReviewCandidate): unknown => {
    if ("normalized_value" in candidate) {
      const normalized = candidate as NormalizedCandidate;
      return normalized.target_kind === "record" ? `${normalized.record_type ?? "record"} (${normalized.fields?.length ?? 0} 个字段)` : normalized.normalized_value;
    }
    return candidate.value;
  };
  const candidateIssues = (candidate: ReviewCandidate) => "issues" in candidate ? candidate.issues : candidate.warnings;
  const conflict = (candidate: ReviewCandidate) => "status" in candidate ? candidate.status === "conflict" : candidate.existing_value_conflict;
  const decide = (candidateId: string, decision: Decision, value?: string) => setCandidates((items) => items.map((item) => item.candidate_id === candidateId ? { ...item, ...(value === undefined ? {} : { _value: value }), _decision: decision } as unknown as ReviewCandidate : item));

  const confirm = async () => {
    if (!taskId) return;
    setBusy(true); setMessage(null);
    try {
      const input = {
        task_id: normalizationTaskId ?? taskId,
        profile_id: profileId,
        expected_profile_version: snapshot.profile_version,
        decisions: candidates.flatMap((candidate) => {
          const state = candidate as ReviewCandidate & { _decision?: Decision; _value?: string };
          if (!state._decision) return [];
          return [{ candidate_id: candidate.candidate_id, decision: state._decision, ...(state._value === undefined ? {} : { value: state._value }), user_confirmed: true as const }];
        }),
      };
      const result = normalizationTaskId && client.normalizationConfirm ? await client.normalizationConfirm(input) : client.importConfirm ? await client.importConfirm(input) : null;
      if (!result) return;
      setCandidates([]); setTaskId(null); setNormalizationTaskId(null); setFile(null);
      setMessage(`已写入 ${result.written_field_ids.length} 个字段`); onComplete(result.profile_version);
    } catch (error) { onError(error instanceof Error ? error.message : "确认写入失败"); }
    finally { setBusy(false); }
  };

  const cancel = async () => {
    try {
      if (normalizationTaskId && client.normalizationCancel) await client.normalizationCancel(normalizationTaskId);
      if (taskId && client.importCancel) await client.importCancel(taskId);
    } catch (error) { onError(error instanceof Error ? error.message : "取消失败"); return; }
    setCandidates([]); setTaskId(null); setNormalizationTaskId(null); setFile(null); setMessage("已取消导入");
  };

  if (!client.importPreview || (!client.importConfirm && !client.normalizationConfirm)) return null;
  return <section aria-labelledby="import-title">
    <h2 id="import-title">导入文档</h2>
    <input aria-label="选择 PDF 或 DOCX" type="file" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" onChange={(event) => { setCandidates([]); setTaskId(null); setNormalizationTaskId(null); setMessage(null); setFile(event.target.files?.[0] ?? null); }} disabled={busy || saving} />
    <button type="button" onClick={() => void preview()} disabled={!file || busy || saving}>解析预览</button>
    {message ? <p role="status">{message}</p> : null}
    {candidates.length > 0 ? <>
      <h3>标准化待确认结果</h3>
      {candidates.map((candidate) => {
        const state = (candidate as ReviewCandidate & { _decision?: Decision })._decision;
        const issues = candidateIssues(candidate);
        return <article key={candidate.candidate_id}>
          <p><strong>{candidate.label ?? (candidate as NormalizedCandidate).record_type ?? "候选"}</strong>：{String(candidateValue(candidate))}</p>
          <p>来源：{candidate.source.location ?? candidate.source.document_ref ?? "文档"}；置信度：{Math.round(candidate.confidence * 100)}%</p>
          {"evidence" in candidate && candidate.evidence?.length ? <p>证据：{candidate.evidence.join("；")}</p> : null}
          {conflict(candidate) ? <p role="alert">已有值：{String(candidate.existing_value)}，确认后才会替换</p> : null}
          {"sensitivity" in candidate && candidate.sensitivity !== "normal" ? <p role="alert">敏感字段：需要明确确认</p> : null}
          {"conversion_note" in candidate && candidate.conversion_note ? <p>转换：{candidate.conversion_note}</p> : null}
          {issues?.length ? <p role="alert">问题：{issues.map((item) => item.message).filter(Boolean).join("；")}</p> : null}
          <button type="button" onClick={() => decide(candidate.candidate_id, "accept")} aria-pressed={state === "accept"}>接受</button>
          <input aria-label={`修改 ${candidate.label ?? "候选"}`} defaultValue={String(candidateValue(candidate))} disabled={busy || saving} />
          <button type="button" onClick={(event) => { const input = event.currentTarget.previousElementSibling as HTMLInputElement | null; decide(candidate.candidate_id, "modify", input?.value ?? String(candidateValue(candidate))); }} aria-pressed={state === "modify"}>使用修改值</button>
          <button type="button" onClick={() => decide(candidate.candidate_id, "reject")} aria-pressed={state === "reject"}>拒绝</button>
          <button type="button" onClick={() => decide(candidate.candidate_id, "skip")} aria-pressed={state === "skip"}>跳过</button>
        </article>;
      })}
      <button type="button" onClick={() => void cancel()} disabled={busy || saving}>取消导入</button>
      <button type="button" onClick={() => void confirm()} disabled={busy || saving}>确认写入已接受字段</button>
    </> : null}
  </section>;
}
