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
  validation?: { format?: string; pattern?: string; min_length?: number; max_length?: number; minimum?: number; maximum?: number; allowed_values?: ProfileValue[] };
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
  aliases?: string[];
  validation?: { format?: string; pattern?: string; min_length?: number; max_length?: number; minimum?: number; maximum?: number; allowed_values?: ProfileValue[] };
  created_at?: string;
  updated_at?: string;
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
  /** Reuse these IDs when retrying the same logical mutation. */
  request_id?: string;
  task_id?: string;
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
export interface ProfileFieldSelector {
  id: string;
  scope: "global" | "website" | "application";
  scope_context?: string;
}
export type ProfileDeleteSelection =
  | { field_ids: string[] }
  | { field_values: ProfileFieldSelector[] }
  | { record_ids: string[] }
  | { custom_field_definition_ids: string[] }
  | { delete_all: true };

export interface ProfileDeleteInput {
  /** Reuse these IDs when retrying the same logical mutation. */
  request_id?: string;
  task_id?: string;
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
  | { field_values: ProfileFieldSelector[] }
  | { record_ids: string[] }
  | { scopes: Array<"global" | "website" | "application"> }
  | { all_profile_data: true };

export interface ProfileExportInput {
  /** Reuse these IDs when retrying the same logical mutation. */
  request_id?: string;
  task_id?: string;
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

export interface ImportCandidate {
  candidate_id: string;
  field_id: string;
  label: string;
  field_type: FieldType;
  value: ProfileValue;
  source: { kind: string; document_ref?: string; location?: string; [key: string]: unknown };
  confidence: number;
  requires_confirmation: true;
  sensitivity?: "normal" | "sensitive" | "highly_sensitive";
  existing_value_conflict?: boolean;
  existing_value?: ProfileValue;
  evidence?: string[];
  warnings: Array<{ code?: string; message?: string; severity?: string }>;
}

export interface ImportPreviewResult {
  task_id?: string;
  document_id: string;
  candidates: ImportCandidate[];
  warnings: Array<{ code?: string; message?: string; severity?: string }>;
  ocr_used?: boolean;
  model_used?: boolean;
  remote_data_sent?: boolean;
  consent_recorded?: boolean;
}

export interface ImportConfirmInput {
  request_id?: string;
  task_id: string;
  profile_id: string;
  expected_profile_version: number;
  decisions: Array<{
    candidate_id: string;
    decision: "accept" | "modify" | "reject";
    value?: ProfileValue;
    target_scope?: "global" | "website" | "application";
    user_confirmed: true;
  }>;
}

export interface ImportConfirmResult {
  written_field_ids: string[];
  rejected_candidate_ids: string[];
  profile_version?: number;
  warnings: Array<{ code?: string; message?: string; severity?: string }>;
}
export interface ImportCancelResult { cancelled: boolean; }

export interface NormalizedCandidate {
  candidate_id: string;
  target_kind: "field" | "record";
  field_id?: string;
  label?: string;
  field_type?: FieldType;
  record_type?: "education" | "work" | "internship" | "project" | "unknown";
  fields?: Array<Record<string, unknown>>;
  original_value?: ProfileValue;
  normalized_value: ProfileValue;
  value?: ProfileValue;
  source: { kind: string; document_ref?: string; location?: string; [key: string]: unknown };
  confidence: number;
  status: "new" | "unchanged" | "possible_duplicate" | "conflict" | "unclassified" | "invalid";
  requires_confirmation: true;
  existing_value?: ProfileValue;
  issues: Array<{ code?: string; message?: string; severity?: string; action?: string }>;
}
export interface NormalizationPreviewResult {
  task_id: string;
  source_task_id: string;
  profile_id: string;
  profile_version: number;
  candidates: NormalizedCandidate[];
  model_used: boolean;
  remote_data_sent: boolean;
}
export interface NormalizationConfirmResult { written_field_ids: string[]; rejected_candidate_ids: string[]; profile_version?: number; warnings: Array<{ code?: string; message?: string; severity?: string }>; }


export interface ProfileClient {
  read(profileId: string): Promise<ProfileSnapshot>;
  upsert(input: ProfileUpsertInput): Promise<ProfileSnapshot>;
  delete?(input: ProfileDeleteInput): Promise<ProfileDeleteResult>;
  export?(input: ProfileExportInput): Promise<ProfileExportResult>;
  importPreview?(file: File, taskId?: string): Promise<ImportPreviewResult>;
  importConfirm?(input: ImportConfirmInput): Promise<ImportConfirmResult>;
  importCancel?(taskId: string): Promise<ImportCancelResult>;
  normalizationPreview?(sourceTaskId: string, profileId: string): Promise<NormalizationPreviewResult>;
  normalizationConfirm?(input: ImportConfirmInput): Promise<NormalizationConfirmResult>;
  normalizationCancel?(taskId: string): Promise<ImportCancelResult>;
}

export class ProfileClientError extends Error {
  readonly code?: string;
  readonly retryable: boolean;
  readonly details?: Record<string, unknown>;

  constructor(
    message: string,
    options: { code?: string; retryable?: boolean; details?: Record<string, unknown> } = {},
  ) {
    super(message);
    this.name = "ProfileClientError";
    this.code = options.code;
    this.retryable = options.retryable ?? false;
    this.details = options.details;
  }
}

/** A mutation was accepted, but the follow-up snapshot read failed. */
export class ProfileRefreshError extends Error {
  readonly mutationCommitted = true;

  constructor(cause?: unknown) {
    super("profile mutation committed but refresh failed");
    this.name = "ProfileRefreshError";
    this.cause = cause;
  }

  readonly cause?: unknown;
}

function assertLocalAgentUrl(value: string): string {
  if (typeof value !== "string" || !value || value !== value.trim()) {
    throw new TypeError("baseUrl must be an exact loopback URL");
  }
  let parsed: URL;
  try {
    parsed = new URL(value);
  } catch (cause) {
    throw new TypeError("baseUrl must be an exact loopback URL", { cause });
  }
  const hostname = parsed.hostname.toLowerCase().replace(/^\[|\]$/g, "");
  if (
    parsed.protocol !== "http:"
    || !["127.0.0.1", "localhost", "::1"].includes(hostname)
    || parsed.username
    || parsed.password
    || parsed.search
    || parsed.hash
    || (parsed.pathname !== "" && parsed.pathname !== "/")
  ) {
    throw new TypeError("baseUrl must be an HTTP loopback URL without credentials or a path");
  }
  return parsed.origin;
}

export class HttpProfileClient implements ProfileClient {
  private sequence = 0;

  constructor(
    baseUrl = "http://127.0.0.1:8765",
    private readonly requestPrefix = "extension-profile-request",
    private readonly taskPrefix = "extension-profile-task",
  ) {
    this.baseUrl = assertLocalAgentUrl(baseUrl);
  }

  private readonly baseUrl: string;

  private nextIdentity(operation: string): { request_id: string; task_id: string } {
    const suffix = typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
      ? crypto.randomUUID()
      : `${Date.now()}-${this.sequence++}`;
    return {
      request_id: `${this.requestPrefix}-${operation}-${suffix}`,
      task_id: `${this.taskPrefix}-${operation}-${suffix}`,
    };
  }

  async read(profileId: string): Promise<ProfileSnapshot> {
    const identity = this.nextIdentity("read");
    const response = await fetch(`${this.baseUrl}/v0/profile/read`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        schema_version: "0.1",
        ...identity,
        operation: "profile.read",
        profile_id: profileId,
      }),
    });
    return this.parseResponse<ProfileSnapshot>(response, "profile read failed");
  }

  async upsert(input: ProfileUpsertInput): Promise<ProfileSnapshot> {
    const identity = this.identityFor("upsert", input);
    const response = await fetch(`${this.baseUrl}/v0/profile/upsert`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        schema_version: "0.1",
        ...identity,
        operation: "profile.upsert",
        ...input,
      }),
    });
    await this.parseResponse<Record<string, unknown>>(response, "profile update failed");
    try {
      return await this.read(input.profile_id);
    } catch (error) {
      throw new ProfileRefreshError(error);
    }
  }

  async delete(input: ProfileDeleteInput): Promise<ProfileDeleteResult> {
    const identity = this.identityFor("delete", input);
    const response = await fetch(`${this.baseUrl}/v0/profile/delete`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        schema_version: "0.1",
        ...identity,
        operation: "profile.delete",
        ...input,
      }),
    });
    return this.parseResponse<ProfileDeleteResult>(response, "profile delete failed");
  }

  async export(input: ProfileExportInput): Promise<ProfileExportResult> {
    const identity = this.identityFor("export", input);
    const response = await fetch(`${this.baseUrl}/v0/profile/export`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        schema_version: "0.1",
        ...identity,
        operation: "profile.export",
        ...input,
      }),
    });
    return this.parseResponse<ProfileExportResult>(response, "profile export failed");
  }

  async importPreview(file: File, taskId?: string): Promise<ImportPreviewResult> {
    const identity = this.nextIdentity("import-preview");
    const bytes = new Uint8Array(await file.arrayBuffer());
    let binary = "";
    for (const byte of bytes) binary += String.fromCharCode(byte);
    const contentBase64 = btoa(binary);
    const response = await fetch(`${this.baseUrl}/v0/profile/import/preview`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        schema_version: "0.1",
        ...identity,
        ...(taskId ? { task_id: taskId } : {}),
        operation: "profile.import.preview",
        source: { document_id: `${identity.task_id}-document`, filename: file.name, media_type: file.type || mediaTypeForName(file.name), size_bytes: file.size },
        content_base64: contentBase64,
        consent: { remote_model_allowed: false },
        ocr_mode: "auto",
      }),
    });
    return this.parseResponse<ImportPreviewResult>(response, "document preview failed");
  }

  async importConfirm(input: ImportConfirmInput): Promise<ImportConfirmResult> {
    const identity = this.identityFor("import-confirm", input);
    const response = await fetch(`${this.baseUrl}/v0/profile/import/confirm`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ schema_version: "0.1", ...identity, operation: "profile.import.confirm", ...input }),
    });
    return this.parseResponse<ImportConfirmResult>(response, "document confirmation failed");
  }

  async importCancel(taskId: string): Promise<ImportCancelResult> {
    const identity = this.nextIdentity("import-cancel");
    const response = await fetch(`${this.baseUrl}/v0/profile/import/cancel`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        schema_version: "0.1", ...identity, task_id: taskId,
        operation: "profile.import.cancel",
      }),
    });
    return this.parseResponse<ImportCancelResult>(response, "document cancellation failed");
  }

  async normalizationPreview(sourceTaskId: string, profileId: string): Promise<NormalizationPreviewResult> {
    const identity = this.nextIdentity("normalize-preview");
    const response = await fetch(`${this.baseUrl}/v0/profile/normalize/preview`, {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ schema_version: "0.1", ...identity, operation: "profile.normalize.preview", source_task_id: sourceTaskId, profile_id: profileId }),
    });
    return this.parseResponse<NormalizationPreviewResult>(response, "资料标准化预览失败");
  }

  async normalizationConfirm(input: ImportConfirmInput): Promise<NormalizationConfirmResult> {
    const identity = this.identityFor("normalize-confirm", input);
    const response = await fetch(`${this.baseUrl}/v0/profile/normalize/confirm`, {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ schema_version: "0.1", ...identity, operation: "profile.normalize.confirm", ...input }),
    });
    return this.parseResponse<NormalizationConfirmResult>(response, "资料标准化确认失败");
  }

  async normalizationCancel(taskId: string): Promise<ImportCancelResult> {
    const identity = this.nextIdentity("normalize-cancel");
    const response = await fetch(`${this.baseUrl}/v0/profile/normalize/cancel`, {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ schema_version: "0.1", ...identity, task_id: taskId, operation: "profile.normalize.cancel" }),
    });
    return this.parseResponse<ImportCancelResult>(response, "资料标准化取消失败");
  }

  private identityFor(
    operation: string,
    input: { request_id?: string; task_id?: string },
  ): { request_id: string; task_id: string } {
    const generated = this.nextIdentity(operation);
    return {
      request_id: input.request_id ?? generated.request_id,
      task_id: input.task_id ?? generated.task_id,
    };
  }


  private async parseResponse<T>(response: Response, fallback: string): Promise<T> {
    let payload: { profile?: T; error?: { code?: string; message?: string; retryable?: boolean; details?: Record<string, unknown> } };
    try {
      payload = (await response.json()) as typeof payload;
    } catch {
      // Do not retain or expose a parser exception; it may contain response
      // fragments that are outside the redacted contract boundary.
      throw new ProfileClientError(fallback, { code: "INVALID_FIELD_VALUE" });
    }
    if (!response.ok) {
      throw new ProfileClientError(payload.error?.message ?? fallback, {
        code: payload.error?.code,
        retryable: payload.error?.retryable,
        details: payload.error?.details,
      });
    }
    return (payload.profile ?? payload) as T;
  }
}

function mediaTypeForName(name: string): string {
  const lower = name.toLowerCase();
  if (lower.endsWith(".pdf")) return "application/pdf";
  if (lower.endsWith(".docx")) return "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
  return "application/octet-stream";
}
