import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createMemoryHistory, createRouter } from "vue-router";

import { ApiError } from "@/api/request";
import { useSessionStore } from "@/store/session";

import DeckEditorView from "./editor.vue";


const deckMocks = vi.hoisted(() => ({
  getDraft: vi.fn(),
  updateDraft: vi.fn(),
  confirmDraft: vi.fn(),
  preflightDraft: vi.fn(),
  generate: vi.fn(),
  listTemplates: vi.fn(),
}));

vi.mock("@/modules/decks/api", () => ({
  deckApi: deckMocks,
}));

const slides = ["开场", "分析", "结论"].map((title, index) => ({
  slide_id: `slide-${index + 1}`,
  title,
  purpose: `${title}目标`,
  body: [`${title}要点`],
  speaker_notes: "",
  visual_suggestion: "",
  provenance: [{ kind: "agnes_inference", evidence_ids: [] }],
}));

const draft = {
  draft_id: "draft-1",
  thread_id: "thread-1",
  source_message_id: "message-1",
  revision_id: "revision-1",
  revision: 1,
  status: "draft",
  content: {
    schema_version: "deck-brief.v1",
    topic: "季度复盘",
    audience: "管理层",
    language: "zh-CN",
    style: "专业",
    source_mode: "inspiration",
    skill_code: "ppt.sales-business-review.v1",
    slides,
  },
  content_checksum: "a".repeat(64),
  preflight_snapshot: null,
  generation_task_id: null,
  confirmed_at: null,
  replayed: false,
  template_snapshot: {
    template_code: "ppt.operating-review.v1",
    version: "1.0.0",
    checksum: "a".repeat(64),
  },
};

async function mountEditor() {
  const pinia = createPinia();
  setActivePinia(pinia);
  useSessionStore().setTokens({
    access_token: "access",
    refresh_token: "refresh",
    token_type: "bearer",
  });
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      {
        path: "/decks/:draftId",
        name: "deck-editor",
        component: DeckEditorView,
      },
      {
        path: "/generations/:taskId",
        name: "generation-detail",
        component: { template: "<div />" },
      },
    ],
  });
  await router.push("/decks/draft-1");
  await router.isReady();
  const wrapper = mount(DeckEditorView, {
    global: { plugins: [pinia, router] },
  });
  await flushPromises();
  return { wrapper, router };
}

describe("Deck editor", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    deckMocks.getDraft.mockResolvedValue(structuredClone(draft));
    deckMocks.updateDraft.mockImplementation(async (_id, payload) => ({
      ...structuredClone(draft),
      revision: 2,
      content: payload.content,
    }));
    deckMocks.confirmDraft.mockResolvedValue({
      ...structuredClone(draft),
      status: "confirmed",
    });
    deckMocks.preflightDraft.mockResolvedValue({
      ...structuredClone(draft),
      status: "ready",
      preflight_snapshot: {
        estimated_credits: 800,
        has_blockers: false,
        conflicts: [],
      },
    });
    deckMocks.generate.mockResolvedValue({ task_id: "task-1" });
    deckMocks.listTemplates.mockResolvedValue([
      {
        template_code: "ppt.operating-review.v1",
        version: "1.0.0",
        checksum: "a".repeat(64),
        name: "经营复盘",
        category: "operating-review",
        style_keywords: ["复盘"],
        use_cases: ["经营复盘"],
        compatible_skills: ["ppt.sales-business-review.v1"],
        cover_url: "/template-previews/ppt.operating-review.v1/cover.svg",
        representative_urls: [
          "/template-previews/ppt.operating-review.v1/representative.svg",
        ],
      },
      {
        template_code: "ppt.data-story.v1",
        version: "1.0.0",
        checksum: "b".repeat(64),
        name: "数据叙事",
        category: "data-story",
        style_keywords: ["数据"],
        use_cases: ["指标分析"],
        compatible_skills: [
          "ppt.sales-business-review.v1",
          "ppt.knowledge-education.v1",
        ],
        cover_url: "/template-previews/ppt.data-story.v1/cover.svg",
        representative_urls: [
          "/template-previews/ppt.data-story.v1/representative.svg",
        ],
      },
    ]);
  });

  it("reorders, duplicates, deletes, and saves a new immutable revision", async () => {
    const { wrapper } = await mountEditor();

    await wrapper.get("[data-testid='slide-down-0']").trigger("click");
    expect(wrapper.findAll("[data-testid='slide-title']")[0].element).toHaveProperty(
      "value",
      "分析",
    );
    await wrapper.get("[data-testid='slide-duplicate-0']").trigger("click");
    expect(wrapper.findAll("[data-testid='slide-card']")).toHaveLength(4);
    await wrapper.get("[data-testid='slide-delete-1']").trigger("click");
    expect(wrapper.findAll("[data-testid='slide-card']")).toHaveLength(3);
    await wrapper.get("[data-testid='deck-save']").trigger("click");
    await flushPromises();

    expect(deckMocks.updateDraft).toHaveBeenCalledWith(
      "draft-1",
      expect.objectContaining({
        expected_revision: 1,
        content: expect.objectContaining({
          slides: expect.arrayContaining([
            expect.objectContaining({ title: "分析" }),
          ]),
        }),
      }),
      "access",
    );
    expect(wrapper.text()).toContain("Revision 2");
  });

  it("previews and freezes a compatible template in a new revision", async () => {
    deckMocks.updateDraft.mockImplementation(async (_id, payload) => ({
      ...structuredClone(draft),
      revision: 2,
      content: payload.content,
      template_snapshot: {
        template_code: payload.template_code,
        version: "1.0.0",
        checksum: "b".repeat(64),
      },
    }));
    const { wrapper } = await mountEditor();

    expect(deckMocks.listTemplates).toHaveBeenCalledWith("access");
    await wrapper
      .get("[data-testid='deck-template-select']")
      .setValue("ppt.data-story.v1");
    expect(
      wrapper.get("[data-testid='deck-template-preview']").attributes("src"),
    ).toBe("/template-previews/ppt.data-story.v1/cover.svg");
    await wrapper.get("[data-testid='deck-save']").trigger("click");
    await flushPromises();

    expect(deckMocks.updateDraft).toHaveBeenCalledWith(
      "draft-1",
      expect.objectContaining({
        expected_revision: 1,
        template_code: "ppt.data-story.v1",
      }),
      "access",
    );
    expect(wrapper.text()).toContain("Revision 2");
  });

  it("confirms, preflights, and submits the authoritative generation task", async () => {
    const { wrapper, router } = await mountEditor();

    await wrapper.get("[data-testid='deck-confirm']").trigger("click");
    await flushPromises();
    await wrapper.get("[data-testid='deck-preflight']").trigger("click");
    await flushPromises();
    expect(wrapper.text()).toContain("预计 800 Credits");
    await wrapper.get("[data-testid='deck-generate']").trigger("click");
    await flushPromises();

    expect(deckMocks.generate).toHaveBeenCalledWith(
      "draft-1",
      { expected_revision: 1, accepted_estimated_credits: 800 },
      expect.any(String),
      "access",
    );
    expect(router.currentRoute.value.fullPath).toBe("/generations/task-1");
  });

  it("shows a stale revision gate and lets the user reload", async () => {
    deckMocks.updateDraft.mockRejectedValue(
      new ApiError("deck_revision_stale", "revision stale", null, 409),
    );
    const { wrapper } = await mountEditor();

    await wrapper.get("[data-testid='deck-save']").trigger("click");
    await flushPromises();

    expect(wrapper.get("[data-testid='deck-stale']").text()).toContain(
      "Draft 已被更新",
    );
    await wrapper.get("[data-testid='deck-reload']").trigger("click");
    await flushPromises();
    expect(deckMocks.getDraft).toHaveBeenCalledTimes(2);
  });
});
