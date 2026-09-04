import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ProfilePage } from "../../src/options/ProfilePage";
import type { ProfileClient, ProfileSnapshot } from "../../src/options/profileClient";

const timestamp = "2099-01-01T00:00:00Z";
const snapshot: ProfileSnapshot = {
  profile_id: "profile-synthetic-record-types",
  profile_version: 1,
  is_empty: false,
  fields: [], records: [{
    record_id: "education-synthetic-types",
    record_type: "education",
    position: 0,
    fields: [
      { id: "education.school_name", label: "院校", field_type: "text", value: "Synthetic U", scope: "global", sensitivity: "normal", requires_confirmation: false, confirmed: true, source: { kind: "manual" }, updated_at: timestamp },
      { id: "education.score", label: "成绩", field_type: "number", value: 95, scope: "global", sensitivity: "normal", requires_confirmation: false, confirmed: true, source: { kind: "import" }, updated_at: timestamp },
      { id: "education.full_time", label: "全日制", field_type: "boolean", value: true, scope: "global", sensitivity: "normal", requires_confirmation: false, confirmed: true, source: { kind: "manual" }, updated_at: timestamp },
    ],
    confirmed: true, created_at: timestamp, updated_at: timestamp,
  }],
  field_definitions: [], created_at: timestamp, updated_at: timestamp,
};

describe("RecordEditor typed controls and metadata", () => {
  it("serializes edited number and boolean values and shows nested metadata", async () => {
    const client: ProfileClient & { read: ReturnType<typeof vi.fn>; upsert: ReturnType<typeof vi.fn> } = {
      read: vi.fn().mockResolvedValue(snapshot),
      upsert: vi.fn().mockResolvedValue(snapshot),
    };
    render(<ProfilePage client={client} profileId={snapshot.profile_id} />);
    fireEvent.click(await screen.findByRole("button", { name: /编辑/ }));
    fireEvent.change(screen.getByRole("spinbutton", { name: "成绩" }), { target: { value: "98" } });
    fireEvent.change(screen.getByRole("combobox", { name: "全日制" }), { target: { value: "false" } });
    fireEvent.click(screen.getByRole("button", { name: /保存记录/ }));
    await waitFor(() => expect(client.upsert).toHaveBeenCalledTimes(1));
    const fields = client.upsert.mock.calls[0][0].records[0].fields;
    expect(fields.find((field: { id: string }) => field.id === "education.score").value).toBe(98);
    expect(fields.find((field: { id: string }) => field.id === "education.full_time").value).toBe(false);

    expect(screen.getByText(/来源：导入/)).toBeInTheDocument();
    expect(screen.getAllByText(/确认状态：已确认/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/敏感级别：普通/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/使用范围：全部资料/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/更新时间：2099-01-01/).length).toBeGreaterThan(0);
  });
});
