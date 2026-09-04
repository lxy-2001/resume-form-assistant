import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ProfilePage } from "../../src/options/ProfilePage";
import type { ProfileClient, ProfileSnapshot } from "../../src/options/profileClient";

const emptySnapshot: ProfileSnapshot = {
  profile_id: "profile-synthetic-f001-001",
  profile_version: 0,
  is_empty: true,
  fields: [],
  records: [],
  field_definitions: [],
  created_at: "2099-01-01T00:00:00Z",
  updated_at: "2099-01-01T00:00:00Z",
};

const populatedSnapshot: ProfileSnapshot = {
  ...emptySnapshot,
  profile_version: 1,
  is_empty: false,
  fields: [
    {
      id: "person.full_name",
      label: "姓名",
      field_type: "text",
      value: "Synthetic Test Person",
      scope: "global",
      sensitivity: "normal",
      requires_confirmation: false,
      confirmed: true,
      source: { kind: "manual" },
      updated_at: "2099-01-01T00:00:00Z",
    },
  ],
};

function clientFor(snapshot: ProfileSnapshot): ProfileClient & {
  read: ReturnType<typeof vi.fn>;
  upsert: ReturnType<typeof vi.fn>;
} {
  return {
    read: vi.fn().mockResolvedValue(snapshot),
    upsert: vi.fn().mockResolvedValue({
      ...populatedSnapshot,
      profile_version: snapshot.profile_version + 1,
    }),
  };
}

describe("ProfilePage", () => {
  it("loads and presents an accessible empty state", async () => {
    const client = clientFor(emptySnapshot);

    render(<ProfilePage client={client} profileId={emptySnapshot.profile_id} />);

    expect(screen.getByRole("status")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText(/暂无资料|资料为空/)).toBeInTheDocument());
    expect(client.read).toHaveBeenCalledWith(emptySnapshot.profile_id);
  });

  it("edits a field and saves with the loaded version and confirmation", async () => {
    const client = clientFor(populatedSnapshot);
    render(<ProfilePage client={client} profileId={populatedSnapshot.profile_id} />);

    const input = await screen.findByLabelText("姓名");
    fireEvent.change(input, { target: { value: "Updated Synthetic Person" } });
    fireEvent.click(screen.getByRole("button", { name: /保存/ }));

    await waitFor(() => expect(client.upsert).toHaveBeenCalledTimes(1));
    expect(client.upsert.mock.calls[0][0]).toMatchObject({
      profile_id: populatedSnapshot.profile_id,
      expected_profile_version: 1,
      user_confirmed: true,
    });
  });

  it("rejects blank input locally without writing", async () => {
    const client = clientFor(populatedSnapshot);
    render(<ProfilePage client={client} profileId={populatedSnapshot.profile_id} />);

    const input = await screen.findByLabelText("姓名");
    fireEvent.change(input, { target: { value: "   " } });
    fireEvent.click(screen.getByRole("button", { name: /保存/ }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/不能为空|必填/);
    expect(client.upsert).not.toHaveBeenCalled();
  });

  it("cancels unsaved changes and preserves the loaded value", async () => {
    const client = clientFor(populatedSnapshot);
    render(<ProfilePage client={client} profileId={populatedSnapshot.profile_id} />);

    const input = await screen.findByLabelText("姓名");
    fireEvent.change(input, { target: { value: "Unsaved Synthetic Edit" } });
    fireEvent.click(screen.getByRole("button", { name: /取消/ }));

    expect(input).toHaveValue("Synthetic Test Person");
    expect(client.upsert).not.toHaveBeenCalled();
  });

  it("offers a retry when the initial profile read fails", async () => {
    const client = clientFor(emptySnapshot);
    client.read.mockRejectedValueOnce(new Error("offline")).mockResolvedValueOnce(emptySnapshot);
    render(<ProfilePage client={client} profileId={emptySnapshot.profile_id} />);

    expect(await screen.findByRole("alert")).toHaveTextContent(/读取失败/);
    fireEvent.click(screen.getByRole("button", { name: "重试读取" }));

    await waitFor(() => expect(client.read).toHaveBeenCalledTimes(2));
    expect(await screen.findByText(/暂无资料|资料为空/)).toBeInTheDocument();
  });

  it("reuses one mutation identity when a save is retried", async () => {
    const client = clientFor(populatedSnapshot);
    client.upsert
      .mockRejectedValueOnce(new Error("temporary failure"))
      .mockResolvedValueOnce({ ...populatedSnapshot, profile_version: 2 });
    render(<ProfilePage client={client} profileId={populatedSnapshot.profile_id} />);

    const input = await screen.findByLabelText("姓名");
    fireEvent.change(input, { target: { value: "Retry Synthetic Person" } });
    fireEvent.click(screen.getByRole("button", { name: /保存/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/保存失败/);

    fireEvent.click(screen.getByRole("button", { name: "重试" }));
    await waitFor(() => expect(client.upsert).toHaveBeenCalledTimes(2));
    const first = client.upsert.mock.calls[0][0] as { request_id?: string; task_id?: string };
    const second = client.upsert.mock.calls[1][0] as { request_id?: string; task_id?: string };
    expect(second.request_id).toBe(first.request_id);
    expect(second.task_id).toBe(first.task_id);
  });
});
