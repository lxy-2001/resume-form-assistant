import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ProfilePage } from "../../src/options/ProfilePage";
import type { ProfileClient, ProfileSnapshot } from "../../src/options/profileClient";

const timestamp = "2099-01-01T00:00:00Z";
const snapshot: ProfileSnapshot = {
  profile_id: "profile-synthetic-f001-a11y",
  profile_version: 1,
  is_empty: false,
  fields: [{
    id: "person.full_name",
    label: "姓名",
    field_type: "text",
    value: "Synthetic Test Person",
    scope: "global",
    sensitivity: "normal",
    requires_confirmation: false,
    confirmed: true,
    source: { kind: "manual" },
    updated_at: timestamp,
  }],
  records: [],
  field_definitions: [],
  created_at: timestamp,
  updated_at: timestamp,
};

function clientFor(): ProfileClient {
  return {
    read: vi.fn().mockResolvedValue(snapshot),
    upsert: vi.fn().mockResolvedValue(snapshot),
    delete: vi.fn().mockResolvedValue({
      profile_id: snapshot.profile_id,
      profile_version: 2,
      deleted_scope: "all",
      deleted_field_ids: [],
      deleted_record_ids: [],
      all_data_deleted: true,
    }),
    export: vi.fn().mockResolvedValue({
      profile_id: snapshot.profile_id,
      profile_version: snapshot.profile_version,
      format: "json",
      destination_display_name: "profile-export.json",
      exported_field_count: 1,
      exported_record_count: 0,
    }),
  };
}

describe("ProfilePage accessibility requirements", () => {
  it("keeps controls labelled and keyboard-focusable in DOM order", async () => {
    render(<ProfilePage client={clientFor()} profileId={snapshot.profile_id} />);

    expect(await screen.findByRole("main", { name: "我的简历资料" })).toBeInTheDocument();
    expect(screen.getByLabelText("姓名")).toBeInTheDocument();
    const controls = screen.getAllByRole("button");
    expect(controls.length).toBeGreaterThan(0);
    expect(controls.every((control) => control.getAttribute("type") === "button")).toBe(true);
    expect(controls.every((control) => control.tabIndex >= 0)).toBe(true);
  });

  it("exposes a labelled modal and an alert for recoverable lifecycle errors", async () => {
    const client = clientFor();
    client.export = vi.fn().mockRejectedValue(new Error("local export failed"));
    render(<ProfilePage client={client} profileId={snapshot.profile_id} />);

    fireEvent.click(await screen.findByRole("button", { name: "导出资料" }));
    expect(screen.getByRole("dialog", { name: "导出资料" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "确认导出" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("导出失败");
  });
});
