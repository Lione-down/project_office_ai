export interface ProjectSummary {
  project_id: string;
  name: string;
  is_default: boolean;
  is_archived: boolean;
  created_at: string;
  updated_at: string;
}

export interface AssetSummary {
  asset_id: string;
  project_id: string;
  original_filename: string;
  file_category: string;
  mime_type: string;
  byte_size: number;
  sha256: string;
  processing_status: string;
  parser_name: string | null;
  parser_version: string | null;
  processing_warnings: string[];
  processing_error_code: string | null;
  processing_error_message: string | null;
  manifest_status: string | null;
  manifest_schema_version: string | null;
  evidence_engine_version: string | null;
  evidence_warning_count: number | null;
  evidence_blocker_count: number | null;
  quality_status: string | null;
  created_at: string;
  updated_at: string;
}

export interface SkillSummary {
  skill_code: string;
  version: string;
  display_name: string;
  description: string;
  output_kind: "pptx" | "xlsx";
  status: string;
}

export interface ModelSummary {
  model_id: string;
  provider_id: string;
  credential_id: string;
  model_code: string;
  display_name: string;
  capabilities: Record<string, unknown>;
  context_window: number;
  max_output_tokens: number;
  user_visible: boolean;
  is_recommended: boolean;
  credit_multiplier: string;
  allowed_skills: string[];
  status: string;
}

export interface TermLibrarySummary {
  library_id: string;
  version: number;
  name: string;
  status: string;
}

export interface WorkspaceOptions {
  projects: ProjectSummary[];
  assets: AssetSummary[];
  skills: SkillSummary[];
  models: ModelSummary[];
  termLibraries: TermLibrarySummary[];
}

export interface BriefGenerationSelection {
  project_id: string;
  asset_ids: string[];
  term_library_versions: Array<{
    library_id: string;
    version: number;
  }>;
  skill_codes: string[];
  model_id: string;
  goal: string;
  audience: string;
  must_include: string[];
  must_exclude: string[];
}

export interface GeneratedBrief {
  brief_id: string;
  brief_group_id: string;
  revision: number;
  status: string;
}

export interface GenerationStep {
  step_key: string;
  output_kind: "pptx" | "xlsx";
  status: string;
  attempt: number;
  estimated_credits: number;
  error_category: string | null;
  output_asset_id: string | null;
  asset_version: string | null;
  quality_status: string | null;
  download_allowed: boolean;
  quality_report_schema_version: string | null;
}

export interface GenerationTask {
  task_id: string;
  brief_id: string;
  status: string;
  progress: number;
  estimated_credits: number;
  settled_credits: number;
  error_category: string | null;
  cancel_requested: boolean;
  steps: GenerationStep[];
  replayed: boolean;
}

export interface GenerationOutput {
  output_kind: "pptx" | "xlsx";
  status: string;
  estimated_credits: number;
  error_category: string | null;
  asset_id: string | null;
  asset_version: string | null;
  quality_status: string | null;
  download_allowed: boolean;
  quality_report_schema_version: string | null;
}

export interface GenerationOutputs {
  outputs: GenerationOutput[];
}

export interface CreditBalance {
  balance: number;
}

export interface CreditLedger {
  entries: Array<{
    entry_id: string;
    task_id: string | null;
    entry_type: string;
    amount: number;
    balance_after: number;
    created_at: string;
  }>;
}
