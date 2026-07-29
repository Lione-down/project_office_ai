export type DeckSourceMode = "inspiration" | "materials" | "mixed";
export type DeckSkillCode =
  | "ppt.sales-business-review.v1"
  | "ppt.knowledge-education.v1";

export interface DeckProvenance {
  kind: "user_input" | "agnes_inference" | "source_evidence";
  evidence_ids: string[];
}

export interface DeckSlide {
  slide_id: string;
  title: string;
  purpose: string;
  body: string[];
  speaker_notes: string;
  visual_suggestion: string;
  visual_direction?: {
    schema_version: "ppt.visual-director.v1";
    kind: "none" | "diagram" | "chart" | "illustration" | "photo";
    prompt: string;
    requested_size: "1K" | "2K" | "3K" | "4K";
    requested_ratio:
      | "1:1"
      | "3:4"
      | "4:3"
      | "16:9"
      | "9:16"
      | "2:3"
      | "3:2"
      | "21:9";
    crop_mode: "contain" | "cover";
    alt_text: string;
  };
  provenance: DeckProvenance[];
}

export interface DeckBrief {
  schema_version: "deck-brief.v1";
  topic: string;
  audience: string;
  language: "zh-CN";
  style: string;
  source_mode: DeckSourceMode;
  skill_code: DeckSkillCode;
  slides: DeckSlide[];
}

export interface DeckDraft {
  draft_id: string;
  thread_id: string;
  source_message_id: string;
  revision_id: string;
  revision: number;
  status: string;
  content: DeckBrief;
  content_checksum: string;
  template_snapshot: {
    template_code: string;
    version: "1.0.0";
    checksum: string;
  } | null;
  preflight_snapshot: {
    estimated_credits: number;
    has_blockers: boolean;
    conflicts: Array<{
      code: string;
      level: string;
      message: string;
    }>;
  } | null;
  generation_task_id: string | null;
  confirmed_at: string | null;
  media_jobs: MediaJob[];
  replayed: boolean;
}

export interface ImageJob {
  kind: "image";
  media_job_id: string;
  workflow_task_id: string;
  draft_revision_id: string;
  slide_id: string;
  action: "generate" | "replace" | "regenerate";
  status: string;
  progress: number;
  model_snapshot: Record<string, unknown>;
  capability_snapshot: Record<string, unknown>;
  pricing_snapshot: Record<string, unknown>;
  prompt_hash: string;
  requested_size: "1K" | "2K" | "3K" | "4K";
  requested_ratio: string;
  crop_mode: "contain" | "cover";
  alt_text: string;
  actual_width: number | null;
  actual_height: number | null;
  output_asset: {
    asset_id: string;
    version: number;
    mime_type: string;
    byte_size: number;
    sha256: string;
    width: number;
    height: number;
  } | null;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  replayed: boolean;
}

export interface VideoJob {
  kind: "video";
  media_job_id: string;
  workflow_task_id: string;
  draft_revision_id: string;
  slide_id: string;
  action: "generate" | "replace" | "regenerate";
  mode: "text-to-video";
  status: string;
  progress: number;
  provider_job_id: string | null;
  model_snapshot: Record<string, unknown>;
  capability_snapshot: Record<string, unknown>;
  pricing_snapshot: Record<string, unknown>;
  prompt_hash: string;
  requested_width: number;
  requested_height: number;
  requested_num_frames: number;
  requested_frame_rate: number;
  actual_width: number | null;
  actual_height: number | null;
  actual_duration_seconds: number | null;
  output_video: {
    asset_id: string;
    version: number;
    mime_type: "video/mp4";
    byte_size: number;
    sha256: string;
    width: number;
    height: number;
    duration_seconds: number;
    container: "mp4";
    codec: "h264";
    download_path: string;
    preview_path: string;
  } | null;
  poster: {
    asset_id: string;
    version: number;
    mime_type: "image/png";
    byte_size: number;
    sha256: string;
    width: number;
    height: number;
    preview_path: string;
  } | null;
  embedding_enabled: false;
  fallback_mode: "poster_and_attachment";
  error_code: string | null;
  error_message: string | null;
  next_poll_after_seconds: number | null;
  created_at: string;
  updated_at: string;
  replayed: boolean;
}

export type MediaJob = ImageJob | VideoJob;

export interface ImageJobCreateInput {
  expected_revision: number;
  slide_id: string;
  action: "generate" | "replace" | "regenerate";
  prompt: string;
  alt_text: string;
  model_id: string;
  requested_size: "1K" | "2K" | "3K" | "4K";
  requested_ratio: string;
  crop_mode: "contain" | "cover";
  confirmed: true;
  accepted_estimated_credits: number;
  supersedes_job_id?: string;
}

export interface VideoJobCreateInput {
  expected_revision: number;
  slide_id: string;
  action: "generate" | "replace" | "regenerate";
  mode: "text-to-video";
  prompt: string;
  negative_prompt?: string;
  model_id: string;
  width: number;
  height: number;
  num_frames: number;
  frame_rate: number;
  confirmed: true;
  accepted_estimated_credits: number;
  embed_requested: false;
  supersedes_job_id?: string;
}

export interface DeckCreateInput {
  project_id: string;
  model_id: string;
  topic: string;
  audience: string;
  slide_count: number;
  language: "zh-CN";
  style: string;
  source_mode: DeckSourceMode;
  skill_code: DeckSkillCode;
  asset_ids: string[];
}

export interface DeckUpdateInput {
  expected_revision: number;
  content: DeckBrief;
  template_code?: string;
}

export interface DeckGenerationResult {
  task_id: string;
}
