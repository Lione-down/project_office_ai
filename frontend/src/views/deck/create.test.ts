import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createMemoryHistory, createRouter } from "vue-router";

import { useSessionStore } from "@/store/session";

import DeckCreateView from "./create.vue";


const mocks = vi.hoisted(() => ({
  loadOptions: vi.fn(),
  createDraft: vi.fn(),
}));

vi.mock("@/modules/workspace/api", () => ({
  workspaceApi: { loadOptions: mocks.loadOptions },
}));
vi.mock("@/modules/decks/api", () => ({
  deckApi: { createDraft: mocks.createDraft },
}));

async function mountCreate() {
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
        path: "/decks/new",
        name: "deck-create",
        component: DeckCreateView,
      },
      {
        path: "/decks/:draftId",
        name: "deck-editor",
        component: { template: "<div />" },
      },
    ],
  });
  await router.push(
    "/decks/new?messageId=message-1&modelId=model-1",
  );
  await router.isReady();
  const wrapper = mount(DeckCreateView, {
    global: { plugins: [pinia, router] },
  });
  await flushPromises();
  return { wrapper, router };
}

describe("Deck creation gate", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.loadOptions.mockResolvedValue({
      projects: [
        {
          project_id: "project-1",
          name: "季度经营",
          is_default: true,
          is_archived: false,
        },
      ],
      assets: [],
      skills: [
        {
          skill_code: "ppt.knowledge-education.v1",
          display_name: "知识科普与培训",
          output_kind: "pptx",
          status: "published",
        },
      ],
      models: [
        {
          model_id: "model-1",
          display_name: "Agnes 2.5 Flash",
          status: "active",
          user_visible: true,
          is_recommended: true,
          allowed_skills: ["ppt.knowledge-education.v1"],
        },
      ],
      termLibraries: [],
    });
    mocks.createDraft.mockResolvedValue({ draft_id: "draft-1" });
  });

  it("keeps Skill explicit and submits the selected model and source mode", async () => {
    const { wrapper, router } = await mountCreate();

    await wrapper.findAll("input")[0].setValue("生成式 AI 培训");
    await wrapper.findAll("input")[1].setValue("业务团队");
    await wrapper.get("form").trigger("submit");
    await flushPromises();

    expect(mocks.createDraft).toHaveBeenCalledWith(
      "message-1",
      expect.objectContaining({
        project_id: "project-1",
        model_id: "model-1",
        topic: "生成式 AI 培训",
        audience: "业务团队",
        source_mode: "inspiration",
        skill_code: "ppt.knowledge-education.v1",
      }),
      expect.any(String),
      "access",
    );
    expect(router.currentRoute.value.fullPath).toBe("/decks/draft-1");
  });
});
