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
  options?: Array<{ value: ProfileValue; label: string }>;
  aliases?: string[];
}

/**
 * Return the canonical client-side identity for one scoped field value.
 * A field id may legitimately occur once per scope/context, so id alone is
 * not sufficient for React keys or draft state.
 */
export function profileFieldKey(field: Pick<ProfileField, "id" | "scope" | "scope_context">): string {
  return JSON.stringify([field.id, field.scope, field.scope_context ?? null]);
}

export interface FieldDefinition {
  id: string;
  label: string;
  field_type: FieldType;
  default_sensitivity: "normal" | "sensitive" | "highly_sensitive";
  requires_confirmation: boolean;
  is_custom: boolean;
  allowed_scopes: Array<"global" | "website" | "application">;
  options?: Array<{ value: ProfileValue; label: string }>;
  validation?: { format?: string; pattern?: string; min_length?: number; max_length?: number; minimum?: number; maximum?: number; allowed_values?: ProfileValue[] };
}

export type RecordType = "education" | "work" | "internship" | "project";

export interface ProfileRecord {
  record_id: string;
  record_type: RecordType;
  position: number;
  fields: ProfileField[];
  confirmed: true;
  created_at: string;
  updated_at: string;
}
export interface ProfileSnapshot {
  profile_id: string;
  profile_version: number;
  is_empty: boolean;
  fields: ProfileField[];
  records: ProfileRecord[];
  field_definitions: FieldDefinition[];
  created_at: string;
  updated_at: string;
}

export interface ProfileUpsertInput {
  profile_id: string;
  expected_profile_version: number;
  user_confirmed: true;
  mode?: "merge";
  fields?: ProfileField[];
  records?: ProfileRecord[];
  custom_field_definitions?: FieldDefinition[];
  delete_record_ids?: string[];
  delete_custom_field_definition_ids?: string[];
  record_order?: string[];
  delete_field_ids?: string[];
}
export type ProfileDeleteSelection =
  | { field_ids: string[] }
  | { record_ids: string[] }
  | { custom_field_definition_ids: string[] }
  | { delete_all: true };

export interface ProfileDeleteInput {
  profile_id: string;
  expected_profile_version: number;
  user_confirmed: true;
  selection: ProfileDeleteSelection;
}

export interface ProfileDeleteResult {
  profile_id: string;
  profile_version: number;
  task_state: "completed" | "partial";
  deleted_field_ids: string[];
  deleted_record_ids: string[];
  deleted_custom_field_definition_ids: string[];
  all_data_deleted: boolean;
  cleanup_pending: string[];
  warnings: Array<{ code?: string; message?: string; severity?: string }>;
}

export type ProfileExportSelection =
  | { field_ids: string[] }
  | { record_ids: string[] }
  | { scopes: Array<"global" | "website" | "application"> }
  | { all_profile_data: true };

export interface ProfileExportInput {
  profile_id: string;
  expected_profile_version: number;
  user_confirmed: true;
  selection: ProfileExportSelection;
  format: "json";
  destination: {
    kind: "local_file";
    path: string;
    overwrite_existing: boolean;
    overwrite_confirmed?: true;
  };
}

export interface ProfileExportResult {
  profile_id: string;
  profile_version: number;
  task_state: "completed";
  export_id: string;
  format: "json";
  status: "written";
  destination_display_name: string;
  exported_field_ids: string[];
  exported_record_ids: string[];
  exported_scopes: Array<"global" | "website" | "application">;
  bytes_written: number;
  sha256?: string;
  warnings: Array<{ code?: string; message?: string; severity?: string }>;
}


export interface ProfileClient {
  read(profileId: string): Promise<ProfileSnapshot>;
  upsert(input: ProfileUpsertInput): Promise<ProfileSnapshot>;
  delete?(input: ProfileDeleteInput): Promise<ProfileDeleteResult>;
  export?(input: ProfileExportInput): Promise<ProfileExportResult>;
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

  async delete(input: ProfileDeleteInput): Promise<ProfileDeleteResult> {
    const response = await fetch(`${this.baseUrl}/v0/profile/delete`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        schema_version: "0.1",
        request_id: this.requestId,
        task_id: this.taskId,
        operation: "profile.delete",
        ...input,
      }),
    });
    return this.parseResponse<ProfileDeleteResult>(response, "profile delete failed");
  }

  async export(input: ProfileExportInput): Promise<ProfileExportResult> {
    const response = await fetch(`${this.baseUrl}/v0/profile/export`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        schema_version: "0.1",
        request_id: this.requestId,
        task_id: this.taskId,
        operation: "profile.export",
        ...input,
      }),
    });
    return this.parseResponse<ProfileExportResult>(response, "profile export failed");
  }


  private async parseResponse<T>(response: Response, fallback: string): Promise<T> {
    const payload = (await response.json()) as { profile?: T; error?: { message?: string } };
    if (!response.ok) {
      throw new Error(payload.error?.message ?? fallback);
    }
    return (payload.profile ?? payload) as T;
  }
}
