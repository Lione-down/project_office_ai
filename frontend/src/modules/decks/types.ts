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
  replayed: boolean;
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
}

export interface DeckGenerationResult {
  task_id: string;
}
