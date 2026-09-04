import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ProfilePage } from "../../src/options/ProfilePage";
import type { ProfileClient, ProfileSnapshot } from "../../src/options/profileClient";

const timestamp = "2099-01-01T00:00:00Z";
const profileId = "profile-synthetic-lifecycle";

const snapshot: ProfileSnapshot = {
  profile_id: profileId,
  profile_version: 3,
  is_empty: false,
  fields: [{
    id: "person.full_name",
    label: "姓名",
    field_type: "text",
    value: "Synthetic Person",
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

function clientFor(overrides: Partial<ProfileClient> = {}): ProfileClient & {
  read: ReturnType<typeof vi.fn>;
  upsert: ReturnType<typeof vi.fn>;
  delete: ReturnType<typeof vi.fn>;
  export: ReturnType<typeof vi.fn>;
} {
  return {
    read: vi.fn().mockResolvedValue(snapshot),
    upsert: vi.fn().mockResolvedValue(snapshot),
    delete: vi.fn().mockResolvedValue({
      profile_id: profileId,
      profile_version: 4,
      task_state: "completed",
      deleted_field_ids: ["person.full_name"],
      deleted_record_ids: [],
      deleted_custom_field_definition_ids: [],
      all_data_deleted: false,
      cleanup_pending: [],
      warnings: [],
    }),
    export: vi.fn().mockResolvedValue({
      profile_id: profileId,
      profile_version: 3,
      task_state: "completed",
      export_id: "export-synthetic-lifecycle",
      format: "json",
      status: "written",
      destination_display_name: "profile.json",
      exported_field_ids: ["person.full_name"],
      exported_record_ids: [],
      exported_scopes: ["global"],
      bytes_written: 128,
      warnings: [],
    }),
    ...overrides,
  } as ProfileClient & {
    read: ReturnType<typeof vi.fn>;
    upsert: ReturnType<typeof vi.fn>;
    delete: ReturnType<typeof vi.fn>;
    export: ReturnType<typeof vi.fn>;
  };
}

describe("ProfilePage lifecycle controls", () => {
  it("shows profile metadata and requires confirmation before export", async () => {
    const client = clientFor();
    render(<ProfilePage client={client} profileId={profileId} />);

    await screen.findByLabelText("姓名");
    expect(screen.getByText(/资料版本：3/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "导出资料" }));
    expect(screen.getByRole("dialog", { name: /导出资料/ })).toBeInTheDocument();
    expect(client.export).not.toHaveBeenCalled();

    fireEvent.change(screen.getByRole("textbox", { name: "导出文件路径" }), {
      target: { value: "C:\\Synthetic\\profile.json" },
    });
    fireEvent.click(screen.getByRole("button", { name: "确认导出" }));
    await waitFor(() => expect(client.export).toHaveBeenCalledTimes(1));
    expect(client.export.mock.calls[0][0]).toMatchObject({
      profile_id: profileId,
      expected_profile_version: 3,
      user_confirmed: true,
      selection: { all_profile_data: true },
    });
  });

  it("cancels deletion without calling the client and confirms selected deletion", async () => {
    const client = clientFor();
    render(<ProfilePage client={client} profileId={profileId} />);

    await screen.findByLabelText("姓名");
    fireEvent.click(screen.getByRole("button", { name: "删除资料" }));
    fireEvent.click(screen.getByRole("button", { name: "取消删除" }));
    expect(client.delete).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "删除资料" }));
    fireEvent.change(screen.getByRole("combobox", { name: "删除范围" }), {
      target: { value: "field:person.full_name" },
    });
    fireEvent.click(screen.getByRole("button", { name: "确认删除" }));
    await waitFor(() => expect(client.delete).toHaveBeenCalledTimes(1));
    expect(client.delete.mock.calls[0][0]).toMatchObject({
      profile_id: profileId,
      expected_profile_version: 3,
      user_confirmed: true,
      selection: { field_ids: ["person.full_name"] },
    });
  });

  it("shows a recoverable export failure", async () => {
    const client = clientFor({ export: vi.fn().mockRejectedValue(new Error("failed")) });
    render(<ProfilePage client={client} profileId={profileId} />);

    await screen.findByLabelText("姓名");
    fireEvent.click(screen.getByRole("button", { name: "导出资料" }));
    fireEvent.click(screen.getByRole("button", { name: "确认导出" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/导出失败/);
  });
});
