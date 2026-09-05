import { afterEach, describe, expect, it, vi } from "vitest";

import { HttpProfileClient, ProfileRefreshError } from "../../src/options/profileClient";

const profileId = "profile-synthetic-client";
const snapshot = {
  profile_id: profileId,
  profile_version: 0,
  is_empty: true,
  fields: [],
  records: [],
  field_definitions: [],
  created_at: "2099-01-01T00:00:00Z",
  updated_at: "2099-01-01T00:00:00Z",
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("HttpProfileClient request identities", () => {
  it("sends document bytes to the local preview endpoint with remote consent disabled", async () => {
    let request: Record<string, unknown> | undefined;
    vi.stubGlobal("fetch", vi.fn((_: string, init?: RequestInit) => {
      request = JSON.parse(String(init?.body)) as Record<string, unknown>;
      return Promise.resolve(new Response(JSON.stringify({
        document_id: "doc-1", candidates: [], warnings: [], remote_data_sent: false,
        consent_recorded: false,
      }), { status: 200 }));
    }));

    const file = { name: "resume.pdf", type: "application/pdf", size: 6, arrayBuffer: async () => new TextEncoder().encode("resume").buffer } as unknown as File;
    await new HttpProfileClient().importPreview!(file, "import-task");

    expect(request).toMatchObject({
      operation: "profile.import.preview",
      task_id: "import-task",
      content_base64: "cmVzdW1l",
      consent: { remote_model_allowed: false },
      source: { media_type: "application/pdf", filename: "resume.pdf", size_bytes: 6 },
    });
  });

  it("rejects non-loopback or credential-bearing agent URLs", () => {
    expect(() => new HttpProfileClient("https://evil.example")).toThrow(/loopback/);
    expect(() => new HttpProfileClient("http://user:pass@127.0.0.1:8765")).toThrow(/credentials/);
    expect(() => new HttpProfileClient("http://127.0.0.1:8765/api")).toThrow(/path/);
    expect(() => new HttpProfileClient("http://127.0.0.1:8765")).not.toThrow();
  });

  it("uses a fresh request and task identity for each operation", async () => {
    const requests: Array<{ request_id: string; task_id: string; operation: string }> = [];
    vi.stubGlobal("fetch", vi.fn((_: string, init?: RequestInit) => {
      const body = JSON.parse(String(init?.body)) as {
        request_id: string;
        task_id: string;
        operation: string;
      };
      requests.push(body);
      const payload = body.operation === "profile.read"
        ? { ...snapshot, request_id: body.request_id, task_id: body.task_id, operation: "profile.read.result", task_state: "completed", warnings: [] }
        : { profile_id: profileId, profile_version: 0, task_state: "completed", deleted_field_ids: [], deleted_record_ids: [], deleted_custom_field_definition_ids: [], all_data_deleted: false, cleanup_pending: [], warnings: [] };
      return Promise.resolve(new Response(JSON.stringify(payload), { status: 200 }));
    }));

    const client = new HttpProfileClient();
    await client.read(profileId);
    await client.delete({
      profile_id: profileId,
      expected_profile_version: 0,
      user_confirmed: true,
      selection: { delete_all: true },
    });

    expect(requests).toHaveLength(2);
    expect(new Set(requests.map((request) => request.request_id)).size).toBe(2);
    expect(new Set(requests.map((request) => request.task_id)).size).toBe(2);
    expect(requests[0].request_id).toContain("-read-");
    expect(requests[1].request_id).toContain("-delete-");
  });

  it("preserves caller-supplied mutation identity for a safe retry", async () => {
    const requests: Array<{ request_id: string; task_id: string; operation: string }> = [];
    vi.stubGlobal("fetch", vi.fn((_: string, init?: RequestInit) => {
      const body = JSON.parse(String(init?.body)) as {
        request_id: string;
        task_id: string;
        operation: string;
      };
      requests.push(body);
      return Promise.resolve(new Response(JSON.stringify(
        body.operation === "profile.delete"
          ? { profile_id: profileId, profile_version: 1, task_state: "completed", deleted_field_ids: [], deleted_record_ids: [], deleted_custom_field_definition_ids: [], all_data_deleted: false, cleanup_pending: [], warnings: [] }
          : { ...snapshot, request_id: body.request_id, task_id: body.task_id, operation: "profile.read.result", task_state: "completed", warnings: [] },
      ), { status: 200 }));
    }));
    const client = new HttpProfileClient();
    const input = {
      profile_id: profileId,
      expected_profile_version: 0,
      user_confirmed: true as const,
      selection: { delete_all: true as const },
      request_id: "retry-delete-request",
      task_id: "retry-delete-task",
    };

    await client.delete(input);
    await client.delete(input);

    expect(requests.filter((request) => request.operation === "profile.delete").map(({ request_id, task_id, operation }) => ({ request_id, task_id, operation }))).toEqual([
      { request_id: "retry-delete-request", task_id: "retry-delete-task", operation: "profile.delete" },
      { request_id: "retry-delete-request", task_id: "retry-delete-task", operation: "profile.delete" },
    ]);
  });

  it("reports a committed mutation separately when the refresh read fails", async () => {
    let call = 0;
    vi.stubGlobal("fetch", vi.fn((_: string, init?: RequestInit) => {
      call += 1;
      const body = JSON.parse(String(init?.body)) as { operation: string };
      if (call === 1) {
        return Promise.resolve(new Response(JSON.stringify({
          profile_id: profileId,
          profile_version: 1,
          written_field_ids: [],
          deleted_field_ids: [],
          warnings: [],
        }), { status: 200 }));
      }
      return Promise.resolve(new Response(JSON.stringify({
        error: { code: "STORAGE_UNAVAILABLE", message: "temporarily unavailable", retryable: true },
      }), { status: 503 }));
    }));

    const client = new HttpProfileClient();
    await expect(client.upsert({
      profile_id: profileId,
      expected_profile_version: 0,
      user_confirmed: true,
      fields: [],
    })).rejects.toBeInstanceOf(ProfileRefreshError);
  });
});
