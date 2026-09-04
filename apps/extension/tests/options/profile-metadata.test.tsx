import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ProfilePage } from "../../src/options/ProfilePage";
import type { ProfileClient, ProfileSnapshot } from "../../src/options/profileClient";

const profileId = "profile-synthetic-f001-metadata";
const timestamp = "2099-01-01T00:00:00Z";

const emptyWithCatalog: ProfileSnapshot = {
  profile_id: profileId,
  profile_version: 0,
  is_empty: true,
  fields: [],
  records: [],
  field_definitions: [{
    id: "person.full_name",
    label: "姓名",
    field_type: "text",
    default_sensitivity: "normal",
    requires_confirmation: false,
    is_custom: false,
    allowed_scopes: ["global"],
  }],
  created_at: timestamp,
  updated_at: timestamp,
};

const populated: ProfileSnapshot = {
  ...emptyWithCatalog,
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
};

function clientFor(snapshot: ProfileSnapshot): ProfileClient & {
  read: ReturnType<typeof vi.fn>;
  upsert: ReturnType<typeof vi.fn>;
} {
  return {
    read: vi.fn().mockResolvedValue(snapshot),
    upsert: vi.fn().mockResolvedValue(snapshot),
  };
}

describe("ProfilePage standard fields and metadata", () => {
  it("adds a standard field from the catalog when the profile is empty", async () => {
    const client = clientFor(emptyWithCatalog);
    render(<ProfilePage client={client} profileId={profileId} />);

    await screen.findByText(/暂无资料/);
    fireEvent.click(screen.getByRole("button", { name: /添加标准字段/ }));
    fireEvent.change(screen.getByRole("combobox", { name: /标准字段/ }), {
      target: { value: "person.full_name" },
    });
    fireEvent.change(screen.getByRole("textbox", { name: /字段值/ }), {
      target: { value: "Synthetic Test Person" },
    });
    fireEvent.click(screen.getByRole("button", { name: /确认添加标准字段/ }));

    await waitFor(() => expect(client.upsert).toHaveBeenCalledTimes(1));
    expect(client.upsert.mock.calls[0][0]).toMatchObject({
      profile_id: profileId,
      expected_profile_version: 0,
      user_confirmed: true,
    });
    expect((client.upsert.mock.calls[0][0].fields as Array<{ id: string; value: string }>)[0]).toMatchObject({
      id: "person.full_name",
      value: "Synthetic Test Person",
      source: { kind: "manual" },
    });
  });

  it("shows source, confirmation, sensitivity, scope, and update metadata", async () => {
    const client = clientFor(populated);
    render(<ProfilePage client={client} profileId={profileId} />);

    await screen.findByLabelText("姓名");
    expect(screen.getByText(/来源.*手动/)).toBeInTheDocument();
    expect(screen.getByText(/确认状态.*已确认/)).toBeInTheDocument();
    expect(screen.getByText(/敏感级别.*普通/)).toBeInTheDocument();
    expect(screen.getByText(/使用范围.*全部资料/)).toBeInTheDocument();
    expect(screen.getByText(/更新时间.*2099-01-01/)).toBeInTheDocument();
  });

  it("does not save an edited sensitive field without a second confirmation", async () => {
    const sensitiveSnapshot: ProfileSnapshot = {
      ...populated,
      fields: [{
        ...populated.fields[0],
        sensitivity: "highly_sensitive",
        requires_confirmation: true,
      }],
    };
    const client = clientFor(sensitiveSnapshot);
    const confirmation = vi.spyOn(window, "confirm").mockReturnValue(false);
    render(<ProfilePage client={client} profileId={profileId} />);

    const input = await screen.findByLabelText("姓名");
    fireEvent.change(input, { target: { value: "Changed Sensitive Person" } });
    fireEvent.click(screen.getByRole("button", { name: /^保存$/ }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/取消敏感字段保存/);
    expect(client.upsert).not.toHaveBeenCalled();
    expect(confirmation).toHaveBeenCalled();
    confirmation.mockRestore();
  });
});
