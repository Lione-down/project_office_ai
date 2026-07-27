export interface BriefContentItem {
  content: string;
  source: string;
  evidence_ids: string[];
}

export interface BriefContent {
  goal: string;
  audience: string;
  source_asset_versions: Array<{
    asset_id: string;
    asset_version: string;
  }>;
  must_include: BriefContentItem[];
}

export interface BriefRevision {
  brief_id: string;
  brief_group_id: string;
  revision: number;
  status: "draft" | "preflight" | "needs_resolution" | "queued";
  content: BriefContent;
  content_checksum: string;
  source_snapshot: Record<string, unknown>;
  estimated_credits: number | null;
  confirmed_at: string | null;
}

export interface BriefRevisionUpdate {
  expected_revision: number;
  goal?: string;
  audience?: string;
  resolutions?: ConflictResolution[];
}

export interface ConflictResolution {
  code: string;
  evidence_ids: string[];
  action: "assign_unit" | "confirm_numeric" | "choose_source" | "choose_scope";
  value?: string;
  selected_evidence_id?: string;
}

export interface PreflightConflict {
  code: string;
  level: "auto_merge" | "needs_confirmation" | "blocking" | "incompatible";
  message: string;
  evidence_ids: string[];
}

export interface PlannedOutput {
  skill_code: string;
  kind: "pptx" | "xlsx";
  title: string;
  template_code: string;
  template_version: string;
  estimated_credits: number;
}

export interface PreflightResult {
  brief_id: string;
  brief_group_id: string;
  revision: number;
  status: "preflight" | "needs_resolution" | "queued";
  conflicts: PreflightConflict[];
  outputs: PlannedOutput[];
  credit_multiplier: string | null;
  estimated_credits: number;
  has_blockers: boolean;
  confirmed_at: string | null;
}
