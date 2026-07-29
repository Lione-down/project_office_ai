import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { DeckSlide } from "@/modules/decks/types";

import SlideVideoWorkbench from "./slide-video-workbench.vue";


const deckMocks = vi.hoisted(() => ({
  createVideoJob: vi.fn(),
  cancelMediaJob: vi.fn(),
  previewMediaAsset: vi.fn(),
  downloadMediaAsset: vi.fn(),
}));

vi.mock("@/modules/decks/api", () => ({
  deckApi: deckMocks,
}));

const slide: DeckSlide = {
  slide_id: "slide-2",
  title: "趋势分析",
  purpose: "解释趋势",
  body: ["季度趋势"],
  speaker_notes: "",
  visual_suggestion: "克制的几何运动",
  visual_direction: {
    schema_version: "ppt.visual-director.v1",
    kind: "illustration",
    prompt: "Synthetic geometric motion study",
    requested_size: "2K",
    requested_ratio: "16:9",
    crop_mode: "cover",
    alt_text: "趋势分析视觉",
  },
  provenance: [{ kind: "agnes_inference", evidence_ids: [] }],
};

const videoModel = {
  model_id: "video-model-1",
  provider_id: "provider-1",
  credential_id: "credential-1",
  model_code: "agnes-video-v2.0",
  display_name: "Agnes Video V2.0",
  capabilities: {
    video_generation: true,
    video_embedding: false,
    credit_per_second: 0,
  },
  context_window: 8192,
  max_output_tokens: 1024,
  user_visible: true,
  is_recommended: true,
  credit_multiplier: "1.0000",
  allowed_skills: [],
  status: "active",
};

const runningVideoJob = {
  kind: "video" as const,
  media_job_id: "video-job-1",
  workflow_task_id: "workflow-1",
  draft_revision_id: "revision-1",
  slide_id: "slide-2",
  action: "generate" as const,
  mode: "text-to-video" as const,
  status: "running",
  progress: 42,
  provider_job_id: "video-opaque-1",
  model_snapshot: {},
  capability_snapshot: {},
  pricing_snapshot: {},
  prompt_hash: "0".repeat(64),
  requested_width: 1152,
  requested_height: 768,
  requested_num_frames: 81,
  requested_frame_rate: 24,
  actual_width: null,
  actual_height: null,
  actual_duration_seconds: null,
  embedding_enabled: false as const,
  fallback_mode: "poster_and_attachment" as const,
  output_video: null,
  poster: null,
  error_code: null,
  error_message: null,
  next_poll_after_seconds: 5,
  created_at: "2026-07-29T00:00:00Z",
  updated_at: "2026-07-29T00:00:00Z",
  replayed: false,
};

describe("Slide video workbench", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    deckMocks.createVideoJob.mockResolvedValue({
      kind: "video",
      media_job_id: "video-job-1",
      workflow_task_id: "workflow-1",
      draft_revision_id: "revision-1",
      slide_id: "slide-2",
      action: "generate",
      mode: "text-to-video",
      status: "submitted",
      progress: 0,
      provider_job_id: "video-opaque-1",
      output_video: null,
      poster: null,
      embedding_enabled: false,
      fallback_mode: "poster_and_attachment",
      error_code: null,
      error_message: null,
    });
  });

  it("requires confirmation and submits a bounded text-only request", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const wrapper = mount(SlideVideoWorkbench, {
      props: {
        slide,
        index: 1,
        draftId: "draft-1",
        draftRevision: 1,
        videoModels: [videoModel],
        selectedVideoModelId: "video-model-1",
        isBusy: false,
        accessToken: "access",
      },
    });

    await wrapper.get("[data-testid='slide-video-generate-1']").trigger("click");
    await flushPromises();

    expect(deckMocks.createVideoJob).toHaveBeenCalledWith(
      "draft-1",
      expect.objectContaining({
        slide_id: "slide-2",
        mode: "text-to-video",
        num_frames: 81,
        frame_rate: 24,
        embed_requested: false,
      }),
      expect.any(String),
      "access",
    );
    expect(wrapper.emitted("update:job")?.[0]?.[0]).toMatchObject({
      media_job_id: "video-job-1",
    });
  });

  it("shows authoritative status and a fixed poster plus attachment fallback", () => {
    const wrapper = mount(SlideVideoWorkbench, {
      props: {
        slide,
        index: 1,
        draftId: "draft-1",
        draftRevision: 1,
        videoModels: [videoModel],
        selectedVideoModelId: "video-model-1",
        videoJob: runningVideoJob,
        isBusy: false,
        accessToken: "access",
      },
    });

    expect(wrapper.get("[data-testid='slide-video-status-1']").text()).toContain(
      "42%",
    );
    expect(wrapper.get("[data-testid='slide-video-fallback-1']").text()).toContain(
      "海报帧",
    );
    expect(wrapper.find("[data-testid='slide-video-input-url-1']").exists()).toBe(
      false,
    );
  });
});
