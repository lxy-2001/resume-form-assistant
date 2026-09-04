import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ProfilePage } from "../../src/options/ProfilePage";
import type {
  ProfileClient,
  ProfileField,
  ProfileRecord,
  ProfileSnapshot,
} from "../../src/options/profileClient";

const timestamp = "2099-01-01T00:00:00Z";

function field(overrides: Partial<ProfileField>): ProfileField {
  return {
    id: "person.preferred_location",
    label: "地点",
    field_type: "text",
    value: "Synthetic value",
    scope: "global",
    sensitivity: "normal",
    requires_confirmation: false,
    confirmed: true,
    source: { kind: "manual" },
    updated_at: timestamp,
    ...overrides,
  };
}

function snapshotFor(fields: ProfileField[], records: ProfileRecord[] = []): ProfileSnapshot {
  return {
    profile_id: "profile-synthetic-scope-safety",
    profile_version: 1,
    is_empty: fields.length === 0 && records.length === 0,
    fields,
    records,
    field_definitions: [],
    created_at: timestamp,
    updated_at: timestamp,
  };
}

function clientFor(snapshot: ProfileSnapshot): ProfileClient & {
  read: ReturnType<typeof vi.fn>;
  upsert: ReturnType<typeof vi.fn>;
} {
  return {
    read: vi.fn().mockResolvedValue(snapshot),
    upsert: vi.fn().mockResolvedValue({
      ...snapshot,
      profile_version: snapshot.profile_version + 1,
    }),
  };
}

describe("ProfilePage scoped values and type safety", () => {
  it("keeps same-id values independent when their scopes differ", async () => {
    const snapshot = snapshotFor([
      field({ value: "Global city", scope: "global" }),
      field({
        value: "Website city",
        scope: "website",
        scope_context: "jobs.example.invalid",
      }),
    ]);
    const client = clientFor(snapshot);
    render(<ProfilePage client={client} profileId={snapshot.profile_id} />);

    const inputs = await screen.findAllByRole("textbox");
    fireEvent.change(inputs[1], { target: { value: "Updated website city" } });
    fireEvent.click(screen.getByRole("button", { name: /^保存$/ }));

    await waitFor(() => expect(client.upsert).toHaveBeenCalledTimes(1));
    const savedFields = client.upsert.mock.calls[0][0].fields as ProfileField[];
    expect(savedFields.map((item) => [item.scope, item.value])).toEqual([
      ["global", "Global city"],
      ["website", "Updated website city"],
    ]);
  });

  it("keeps same-id values independent inside one repeatable record", async () => {
    const record: ProfileRecord = {
      record_id: "education-synthetic-scope-001",
      record_type: "education",
      position: 0,
      fields: [
        field({ value: "Global school", scope: "global" }),
        field({
          value: "Website school",
          scope: "website",
          scope_context: "jobs.example.invalid",
        }),
      ],
      confirmed: true,
      created_at: timestamp,
      updated_at: timestamp,
    };
    const snapshot = snapshotFor([], [record]);
    const client = clientFor(snapshot);
    render(<ProfilePage client={client} profileId={snapshot.profile_id} />);

    fireEvent.click(await screen.findByRole("button", { name: "编辑" }));
    const inputs = screen.getAllByRole("textbox", { name: "地点" });
    fireEvent.change(inputs[1], { target: { value: "Updated website school" } });
    fireEvent.click(screen.getByRole("button", { name: "保存记录" }));

    await waitFor(() => expect(client.upsert).toHaveBeenCalledTimes(1));
    const savedFields = client.upsert.mock.calls[0][0].records[0].fields as ProfileField[];
    expect(savedFields.map((item) => [item.scope, item.value])).toEqual([
      ["global", "Global school"],
      ["website", "Updated website school"],
    ]);
  });

  it("does not silently coerce invalid number or boolean edits", async () => {
    const numberSnapshot = snapshotFor([
      field({ id: "education.gpa", label: "绩点", field_type: "number", value: 95 }),
    ]);
    const numberClient = clientFor(numberSnapshot);
    const { unmount } = render(
      <ProfilePage client={numberClient} profileId={numberSnapshot.profile_id} />,
    );

    const numberInput = await screen.findByLabelText("绩点");
    fireEvent.change(numberInput, { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: /^保存$/ }));
    expect(numberClient.upsert).not.toHaveBeenCalled();
    fireEvent.change(numberInput, { target: { value: "not-a-number" } });
    fireEvent.click(screen.getByRole("button", { name: /^保存$/ }));
    expect(numberClient.upsert).not.toHaveBeenCalled();

    unmount();
    const booleanSnapshot = snapshotFor([
      field({ id: "experience.is_current", label: "当前进行中", field_type: "boolean", value: true }),
    ]);
    const booleanClient = clientFor(booleanSnapshot);
    render(<ProfilePage client={booleanClient} profileId={booleanSnapshot.profile_id} />);

    const booleanInput = await screen.findByLabelText("当前进行中");
    fireEvent.change(booleanInput, { target: { value: "not-a-boolean" } });
    fireEvent.click(screen.getByRole("button", { name: /^保存$/ }));
    expect(booleanClient.upsert).not.toHaveBeenCalled();
  });
});
