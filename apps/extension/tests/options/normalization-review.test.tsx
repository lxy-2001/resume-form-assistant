import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { NormalizationReview } from "../../src/options/components/NormalizationReview";
import type { NormalizedCandidate } from "../../src/options/profileClient";

const candidates: NormalizedCandidate[] = [{
  candidate_id: "normalize-1",
  target_kind: "record",
  record_type: "education",
  fields: [{ id: "education.start_date", value: "2020-09-01" }],
  normalized_value: "2020-09-01",
  source: { kind: "import", location: "page 1" },
  confidence: 0.8,
  status: "possible_duplicate",
  requires_confirmation: true,
  issues: [],
  warnings: [{ message: "请核对已有记录" }],
  match_reason: "已有记录包含相同字段值",
}];

describe("NormalizationReview", () => {
  it("exposes keyboard accessible accept, skip, reject and cancel actions", () => {
    const onDecision = vi.fn();
    const onCancel = vi.fn();
    render(<NormalizationReview candidates={candidates} onDecision={onDecision} onCancel={onCancel} />);
    expect(screen.getByText("重复依据：已有记录包含相同字段值")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "跳过" }));
    expect(onDecision).toHaveBeenCalledWith("normalize-1", "skip");
    fireEvent.click(screen.getByRole("button", { name: "取消" }));
    expect(onCancel).toHaveBeenCalledOnce();
  });
});
