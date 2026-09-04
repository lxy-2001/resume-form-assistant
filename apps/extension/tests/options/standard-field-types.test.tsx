import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ProfilePage } from "../../src/options/ProfilePage";
import type { ProfileClient, ProfileSnapshot } from "../../src/options/profileClient";

const timestamp = "2099-01-01T00:00:00Z";

function snapshotFor(fieldDefinition: ProfileSnapshot["field_definitions"][number]): ProfileSnapshot {
  return {
    profile_id: "profile-synthetic-standard-types",
    profile_version: 0,
    is_empty: true,
    fields: [],
    records: [],
    field_definitions: [fieldDefinition],
    created_at: timestamp,
    updated_at: timestamp,
  };
}

function clientFor(snapshot: ProfileSnapshot): ProfileClient & { read: ReturnType<typeof vi.fn>; upsert: ReturnType<typeof vi.fn> } {
  return {
    read: vi.fn().mockResolvedValue(snapshot),
    upsert: vi.fn().mockResolvedValue(snapshot),
  };
}

describe("ProfilePage standard field types and scope", () => {
  it("writes enum values and a required website scope context", async () => {
    const snapshot = snapshotFor({
      id: "application.work_mode",
      label: "工作方式",
      field_type: "enum",
      default_sensitivity: "normal",
      requires_confirmation: false,
      is_custom: false,
      allowed_scopes: ["website"],
      options: [{ value: "remote", label: "远程" }, { value: "onsite", label: "现场" }],
    });
    const client = clientFor(snapshot);
    render(<ProfilePage client={client} profileId={snapshot.profile_id} />);

    fireEvent.click(await screen.findByRole("button", { name: /添加标准字段/ }));
    fireEvent.change(screen.getByRole("combobox", { name: /标准字段/ }), { target: { value: "application.work_mode" } });
    fireEvent.change(screen.getByRole("combobox", { name: /字段值/ }), { target: { value: "remote" } });
    fireEvent.change(screen.getByRole("textbox", { name: /范围标识/ }), { target: { value: "example.invalid" } });
    fireEvent.click(screen.getByRole("button", { name: /确认添加标准字段/ }));

    await waitFor(() => expect(client.upsert).toHaveBeenCalledTimes(1));
    expect(client.upsert.mock.calls[0][0].fields[0]).toMatchObject({
      id: "application.work_mode",
      value: "remote",
      scope: "website",
      scope_context: "example.invalid",
    });
  });

  it("serializes boolean and multivalue standard values", async () => {
    const definitions = [
      { id: "application.needs_sponsorship", label: "需要签证", field_type: "boolean" as const },
      { id: "skills.languages", label: "语言", field_type: "multivalue" as const },
    ];
    for (const definition of definitions) {
      cleanup();
      const snapshot = snapshotFor({
        ...definition,
        default_sensitivity: "normal",
        requires_confirmation: false,
        is_custom: false,
        allowed_scopes: ["global"],
        ...(definition.field_type === "multivalue" ? { options: [{ value: "中文", label: "中文" }, { value: "English", label: "English" }] } : {}),
      });
      const client = clientFor(snapshot);
      render(<ProfilePage client={client} profileId={snapshot.profile_id} />);
      fireEvent.click(await screen.findByRole("button", { name: /添加标准字段/ }));
      fireEvent.change(screen.getByRole("combobox", { name: /标准字段/ }), { target: { value: definition.id } });
      if (definition.field_type === "boolean") {
        fireEvent.change(screen.getByRole("combobox", { name: /字段值/ }), { target: { value: "true" } });
      } else {
        fireEvent.change(screen.getByRole("textbox", { name: /字段值/ }), { target: { value: "中文,English" } });
      }
      fireEvent.click(screen.getByRole("button", { name: /确认添加标准字段/ }));
      await waitFor(() => expect(client.upsert).toHaveBeenCalledTimes(1));
      expect(client.upsert.mock.calls[0][0].fields[0].value).toEqual(definition.field_type === "boolean" ? true : ["中文", "English"]);
    }
  });

  it("uses type-aware controls when editing persisted top-level fields", async () => {
    const snapshot: ProfileSnapshot = {
      profile_id: "profile-synthetic-edit-types",
      profile_version: 2,
      is_empty: false,
      fields: [
        {
          id: "person.gender",
          label: "性别",
          field_type: "enum",
          value: "男",
          scope: "global",
          sensitivity: "normal",
          requires_confirmation: false,
          confirmed: true,
          source: { kind: "manual" },
          updated_at: timestamp,
          options: [{ value: "男", label: "男" }, { value: "女", label: "女" }],
        },
        {
          id: "application.willing_to_travel",
          label: "是否接受出差",
          field_type: "boolean",
          value: true,
          scope: "application",
          scope_context: "application-synthetic",
          sensitivity: "normal",
          requires_confirmation: false,
          confirmed: true,
          source: { kind: "manual" },
          updated_at: timestamp,
        },
      ],
      records: [],
      field_definitions: [],
      created_at: timestamp,
      updated_at: timestamp,
    };
    const client = clientFor(snapshot);
    render(<ProfilePage client={client} profileId={snapshot.profile_id} />);

    fireEvent.change(await screen.findByRole("combobox", { name: "性别" }), {
      target: { value: "女" },
    });
    fireEvent.change(screen.getByRole("combobox", { name: "是否接受出差" }), {
      target: { value: "false" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^保存$/ }));

    await waitFor(() => expect(client.upsert).toHaveBeenCalledTimes(1));
    expect(client.upsert.mock.calls[0][0].fields).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ id: "person.gender", value: "女" }),
        expect.objectContaining({ id: "application.willing_to_travel", value: false }),
      ]),
    );
  });

  it("requires explicit confirmation before adding a sensitive standard field", async () => {
    const snapshot = snapshotFor({
      id: "person.id_number",
      label: "证件号码",
      field_type: "text",
      default_sensitivity: "highly_sensitive",
      requires_confirmation: true,
      is_custom: false,
      allowed_scopes: ["global"],
    });
    const client = clientFor(snapshot);
    vi.spyOn(window, "confirm").mockReturnValue(false);
    render(<ProfilePage client={client} profileId={snapshot.profile_id} />);

    fireEvent.click(await screen.findByRole("button", { name: /添加标准字段/ }));
    fireEvent.change(screen.getByRole("combobox", { name: /标准字段/ }), { target: { value: "person.id_number" } });
    fireEvent.change(screen.getByRole("textbox", { name: /字段值/ }), { target: { value: "SYNTHETIC-ID" } });
    fireEvent.click(screen.getByRole("button", { name: /确认添加标准字段/ }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/取消敏感/);
    expect(client.upsert).not.toHaveBeenCalled();
  });
});
