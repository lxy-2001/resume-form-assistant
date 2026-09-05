import type { NormalizedCandidate } from "../profileClient";

interface NormalizationReviewProps {
  candidates: NormalizedCandidate[];
  onDecision: (candidateId: string, decision: "accept" | "reject") => void;
}

/** Small keyboard-accessible review primitive shared by future import flows. */
export function NormalizationReview({ candidates, onDecision }: NormalizationReviewProps) {
  return <div aria-label="标准化结果审阅">
    {candidates.map((candidate) => <article key={candidate.candidate_id}>
      <p><strong>{candidate.label ?? candidate.record_type ?? "候选"}</strong>：{String(candidate.normalized_value ?? candidate.fields?.length ?? "")}</p>
      <p>来源：{candidate.source.location ?? candidate.source.document_ref ?? "文档"}；置信度：{Math.round(candidate.confidence * 100)}%</p>
      <button type="button" onClick={() => onDecision(candidate.candidate_id, "accept")}>接受</button>
      <button type="button" onClick={() => onDecision(candidate.candidate_id, "reject")}>拒绝</button>
    </article>)}
  </div>;
}
