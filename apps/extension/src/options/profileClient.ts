export type FieldType =
  | "text"
  | "email"
  | "phone"
  | "date"
  | "year"
  | "number"
  | "boolean"
  | "enum"
  | "multivalue"
  | "rich_text"
  | "object";

export type ProfileValue = string | number | boolean | string[] | Record<string, unknown> | null;

export interface ProfileField {
  id: string;
  label: string;
  field_type: FieldType;
  value: ProfileValue;
  scope: "global" | "website" | "application";
  scope_context?: string;
  sensitivity: "normal" | "sensitive" | "highly_sensitive";
  requires_confirmation: boolean;
  confirmed: true;
  source: { kind: string; [key: string]: unknown };
  updated_at: string;
  is_custom?: boolean;
  aliases?: string[];
}

export interface FieldDefinition {
  id: string;
  label: string;
  field_type: FieldType;
  default_sensitivity: "normal" | "sensitive" | "highly_sensitive";
  requires_confirmation: boolean;
  is_custom: boolean;
  allowed_scopes: Array<"global" | "website" | "application">;
}

export interface ProfileSnapshot {
  profile_id: string;
  profile_version: number;
  is_empty: boolean;
  fields: ProfileField[];
  records: unknown[];
  field_definitions: FieldDefinition[];
  created_at: string;
  updated_at: string;
}

export interface ProfileUpsertInput {
  profile_id: string;
  expected_profile_version: number;
  user_confirmed: true;
  mode?: "merge" | "replace";
  fields: ProfileField[];
}

export interface ProfileClient {
  read(profileId: string): Promise<ProfileSnapshot>;
  upsert(input: ProfileUpsertInput): Promise<ProfileSnapshot>;
}

export class HttpProfileClient implements ProfileClient {
  constructor(
    private readonly baseUrl = "http://127.0.0.1:8765",
    private readonly requestId = "extension-profile-request",
    private readonly taskId = "extension-profile-task",
  ) {}

  async read(profileId: string): Promise<ProfileSnapshot> {
    const response = await fetch(`${this.baseUrl}/v0/profile/read`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        schema_version: "0.1",
        request_id: this.requestId,
        task_id: this.taskId,
        operation: "profile.read",
        profile_id: profileId,
      }),
    });
    return this.parseResponse<ProfileSnapshot>(response, "profile read failed");
  }

  async upsert(input: ProfileUpsertInput): Promise<ProfileSnapshot> {
    const response = await fetch(`${this.baseUrl}/v0/profile/upsert`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        schema_version: "0.1",
        request_id: this.requestId,
        task_id: this.taskId,
        operation: "profile.upsert",
        ...input,
      }),
    });
    await this.parseResponse<Record<string, unknown>>(response, "profile update failed");
    return this.read(input.profile_id);
  }

  private async parseResponse<T>(response: Response, fallback: string): Promise<T> {
    const payload = (await response.json()) as { profile?: T; error?: { message?: string } };
    if (!response.ok) {
      throw new Error(payload.error?.message ?? fallback);
    }
    return (payload.profile ?? payload) as T;
  }
}
