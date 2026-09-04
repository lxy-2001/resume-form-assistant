import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ProfilePage } from "../../src/options/ProfilePage";
import type { ProfileClient, ProfileSnapshot } from "../../src/options/profileClient";

const profileId = "profile-synthetic-f001-001";
const timestamp = "2099-01-01T00:00:00Z";

function field(id: string, label: string, value: string) {
  return {
    id,
    label,
    field_type: "text" as const,
    value,
    scope: "global" as const,
    sensitivity: "normal" as const,
    requires_confirmation: false,
    confirmed: true as const,
    source: { kind: "manual" },
    updated_at: timestamp,
  };
}

const educationRecord = {
  record_id: "education-synthetic-001",
  record_type: "education" as const,
  position: 0,
  fields: [field("education.school_name", "院校/培养单位", "Synthetic University")],
  confirmed: true as const,
  created_at: timestamp,
  updated_at: timestamp,
};

const projectRecord = {
  record_id: "project-synthetic-001",
  record_type: "project" as const,
  position: 1,
  fields: [field("experience.organization", "公司/单位/组织", "Synthetic Labs")],
  confirmed: true as const,
  created_at: timestamp,
  updated_at: timestamp,
};

const snapshot: ProfileSnapshot = {
  profile_id: profileId,
  profile_version: 1,
  is_empty: false,
  fields: [],
  records: [educationRecord, projectRecord],
  field_definitions: [],
  created_at: timestamp,
  updated_at: timestamp,
};

type ObservableClient = ProfileClient & {
  read: ReturnType<typeof vi.fn>;
  upsert: ReturnType<typeof vi.fn>;
};

function clientFor(initial: ProfileSnapshot): ObservableClient {
  let current = structuredClone(initial);
  return {
    read: vi.fn().mockResolvedValue(current),
    upsert: vi.fn().mockImplementation(async (input: Record<string, unknown>) => {
      const records = input.records;
      if (Array.isArray(records)) {
        const incomingIds = new Set(records.map((record) => (record as { record_id: string }).record_id));
        current = {
          ...current,
          records: [...current.records.filter((record) => !incomingIds.has((record as { record_id: string }).record_id)), ...records],
        };
      }
      const deleted = input.delete_record_ids;
      if (Array.isArray(deleted)) {
        current = {
          ...current,
          records: current.records.filter(
            (record) => !deleted.includes((record as { record_id: string }).record_id),
          ),
        };
      }
      return current;
    }),
  };
}

function calls(client: ObservableClient): Array<Record<string, unknown>> {
  return client.upsert.mock.calls.map(([input]) => input as Record<string, unknown>);
}

describe("ProfilePage repeated records and custom fields", () => {
  it("adds and edits a record through a confirmed, versioned upsert", async () => {
    const client = clientFor(snapshot);
    render(<ProfilePage client={client} profileId={profileId} />);

    expect(await screen.findByText("Synthetic University")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /新增教育经历/ }));

    const schoolInputs = screen.getAllByRole("textbox", { name: /院校|学校/ });
    fireEvent.change(schoolInputs.at(-1)!, { target: { value: "Synthetic College" } });
    fireEvent.click(screen.getByRole("button", { name: /保存.*(?:记录|经历)/ }));

    await waitFor(() => expect(client.upsert).toHaveBeenCalledTimes(1));
    expect(calls(client)[0]).toMatchObject({
      profile_id: profileId,
      expected_profile_version: 1,
      user_confirmed: true,
    });
    expect((calls(client)[0].records as Array<{ fields: Array<{ value: string }> }>).some(
      (record) => record.fields.some((item) => item.value === "Synthetic College"),
    )).toBe(true);

    const record = screen.getByText("Synthetic University").closest("article") ?? document.body;
    const edit = within(record).queryByRole("button", { name: /编辑/ });
    if (edit) fireEvent.click(edit);
    const editable = screen.getAllByRole("textbox", { name: /院校|学校/ }).at(-1)!;
    fireEvent.change(editable, { target: { value: "Synthetic Graduate School" } });
    fireEvent.click(screen.getByRole("button", { name: /保存.*(?:记录|经历)/ }));

    await waitFor(() => expect(client.upsert).toHaveBeenCalledTimes(2));
    expect(calls(client)[1]).toMatchObject({
      expected_profile_version: 1,
      user_confirmed: true,
    });
  });

  it("reorders records and deletes one by stable id without touching the other", async () => {
    const client = clientFor(snapshot);
    render(<ProfilePage client={client} profileId={profileId} />);

    await screen.findByText("Synthetic Labs");
    const moveUpButtons = screen.getAllByRole("button", { name: /上移/ });
    fireEvent.click(moveUpButtons[1]);
    await waitFor(() => expect(client.upsert).toHaveBeenCalledTimes(1));
    expect(calls(client)[0]).toMatchObject({
      profile_id: profileId,
      expected_profile_version: 1,
      user_confirmed: true,
      record_order: ["project-synthetic-001", "education-synthetic-001"],
    });

    vi.spyOn(window, "confirm").mockReturnValue(true);
    fireEvent.click(screen.getAllByRole("button", { name: /删除/ })[0]);
    await waitFor(() => expect(client.upsert).toHaveBeenCalledTimes(2));
    expect(calls(client)[1]).toMatchObject({
      expected_profile_version: 1,
      user_confirmed: true,
      delete_record_ids: ["education-synthetic-001"],
    });
    expect(screen.getByText("Synthetic Labs")).toBeInTheDocument();
    expect(screen.queryByText("Synthetic University")).not.toBeInTheDocument();
  });

  it("cancels custom-field creation without a permanent write", async () => {
    const client = clientFor(snapshot);
    render(<ProfilePage client={client} profileId={profileId} />);

    fireEvent.click(screen.getByRole("button", { name: /新增自定义字段/ }));
    const label = await screen.findByRole("textbox", { name: /字段名称|名称/ });
    fireEvent.change(label, { target: { value: "未确认的合成字段" } });
    const type = screen.queryByRole("combobox", { name: /字段类型|类型/ });
    if (type) fireEvent.change(type, { target: { value: "enum" } });
    fireEvent.click(screen.getByRole("button", { name: /取消/ }));

    expect(client.upsert).not.toHaveBeenCalled();
    expect(screen.queryByText("未确认的合成字段")).not.toBeInTheDocument();
  });

  it("removes an unsaved new record locally without sending an unknown delete", async () => {
    const client = clientFor(snapshot);
    vi.spyOn(window, "confirm").mockReturnValue(true);
    render(<ProfilePage client={client} profileId={profileId} />);

    await screen.findByText("Synthetic University");
    fireEvent.click(screen.getByRole("button", { name: /新增工作经历/ }));
    const articles = screen.getAllByRole("article");
    const newArticle = articles.at(-1)!;
    fireEvent.click(within(newArticle).getByRole("button", { name: "删除" }));

    await waitFor(() => expect(screen.getAllByRole("article")).toHaveLength(2));
    expect(client.upsert).not.toHaveBeenCalled();
  });

  it("creates a typed custom enum field only after explicit confirmation", async () => {
    const client = clientFor(snapshot);
    render(<ProfilePage client={client} profileId={profileId} />);

    fireEvent.click(screen.getByRole("button", { name: /新增自定义字段/ }));
    fireEvent.change(await screen.findByLabelText("字段名称"), {
      target: { value: "可接受城市" },
    });
    fireEvent.change(screen.getByRole("combobox", { name: /字段类型/ }), { target: { value: "enum" } });
    fireEvent.change(screen.getByRole("textbox", { name: /字段值/ }), { target: { value: "beijing" } });
    fireEvent.change(screen.getByRole("textbox", { name: /允许选项/ }), { target: { value: "beijing,shanghai" } });
    fireEvent.click(screen.getByRole("button", { name: /确认添加/ }));

    await waitFor(() => expect(client.upsert).toHaveBeenCalledTimes(1));
    const input = calls(client)[0];
    expect(input).toMatchObject({
      profile_id: profileId,
      expected_profile_version: 1,
      user_confirmed: true,
    });
    expect(input.custom_field_definitions).toEqual([
      expect.objectContaining({
        label: "可接受城市",
        field_type: "enum",
        is_custom: true,
        requires_confirmation: true,
      }),
    ]);
    expect((input.fields as Array<{ id: string; value: string }>).some((field) => field.id.startsWith("custom.") && field.value === "beijing")).toBe(true);
  });

  it("preserves existing custom definition metadata while editing its value", async () => {
    const customDefinition = {
      id: "custom.metadata-preserved",
      label: "申请备注",
      field_type: "text" as const,
      default_sensitivity: "normal" as const,
      requires_confirmation: true,
      is_custom: true,
      allowed_scopes: ["global" as const],
      aliases: ["备注"],
      validation: { max_length: 120 },
      created_at: timestamp,
      updated_at: timestamp,
    };
    const customSnapshot: ProfileSnapshot = {
      ...snapshot,
      fields: [{
        ...field("custom.metadata-preserved", "申请备注", "原始备注"),
        is_custom: true,
      }],
      field_definitions: [customDefinition],
    };
    const client = clientFor(customSnapshot);
    render(<ProfilePage client={client} profileId={profileId} />);

    fireEvent.click(await screen.findByRole("button", { name: "编辑定义" }));
    fireEvent.change(screen.getByRole("textbox", { name: /字段值/ }), {
      target: { value: "更新后的备注" },
    });
    fireEvent.click(screen.getByRole("button", { name: "确认更新" }));

    await waitFor(() => expect(client.upsert).toHaveBeenCalledTimes(1));
    expect(client.upsert.mock.calls[0][0].custom_field_definitions).toEqual([
      expect.objectContaining({
        aliases: ["备注"],
        validation: { max_length: 120 },
      }),
    ]);
  });
});
