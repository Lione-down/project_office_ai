export type AdminSection =
  | "users"
  | "invites"
  | "providers"
  | "credentials"
  | "models"
  | "tasks"
  | "assets"
  | "credits"
  | "audit-logs";

export interface InviteSummary {
  invite_id: string;
  code_prefix: string;
  max_uses: number;
  used_count: number;
  expires_at: string;
  status: string;
  registration_credit: number;
}

export interface InviteCreate {
  max_uses: number;
  expires_at: string;
  registration_credit: number;
}

export interface ProviderSummary {
  provider_id: string;
  vendor: string;
  display_name: string;
  protocol: string;
  base_url: string;
  status: string;
  default_timeout_seconds: number;
  config: Record<string, unknown>;
}

export interface CredentialSummary {
  credential_id: string;
  provider_id: string;
  name: string;
  masked_key: string;
  status: string;
  rpm_limit: number;
  tpm_limit: number;
  max_concurrency: number;
  rotation_source: string;
  last_test_status: string | null;
}

export interface AdminModelSummary {
  model_id: string;
  provider_id: string;
  credential_id: string;
  model_code: string;
  display_name: string;
  context_window: number;
  max_output_tokens: number;
  user_visible: boolean;
  is_recommended: boolean;
  credit_multiplier: string;
  allowed_skills: string[];
  status: string;
}

export interface AdminOverview {
  providerCount: number;
  credentialCount: number;
  modelCount: number;
  inviteCount: number;
}

export interface AdminUserSummary {
  user_id: string;
  masked_phone: string;
  role: string;
  status: string;
  credit_balance: number;
  must_change_password: boolean;
  created_at: string;
}

export interface AdminAssetSummary {
  asset_id: string;
  owner_user_id: string;
  project_id: string;
  original_filename: string;
  file_category: string;
  mime_type: string;
  byte_size: number;
  sha256: string;
  processing_status: string;
  created_at: string;
}

export interface AuditLogSummary {
  audit_id: string;
  actor_user_id: string | null;
  action: string;
  target_type: string;
  target_id: string | null;
  ip_address: string | null;
  user_agent: string | null;
  reason: string;
  result: string;
  context: Record<string, unknown>;
  trace_id: string;
  created_at: string;
}

export interface SensitivePayload {
  current_password: string;
  reason: string;
}
