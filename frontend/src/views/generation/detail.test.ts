import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createMemoryHistory, createRouter } from "vue-router";

import { useSessionStore } from "@/store/session";

import GenerationDetailView from "./detail.vue";

const workspaceMocks = vi.hoisted(() => ({
  getGeneration: vi.fn(),
  getGenerationOutputs: vi.fn(),
  downloadAsset: vi.fn(),
}));

vi.mock("@/modules/workspace/api", () => ({
  workspaceApi: workspaceMocks,
}));

async function mountDetail(status = "partial_success") {
  workspaceMocks.getGeneration.mockResolvedValue({
    task_id: "task-id",
    brief_id: "brief-id",
    status,
    progress: status === "provider_uncertain" ? 46 : 100,
    estimated_credits: 1600,
    settled_credits: status === "partial_success" ? 800 : 0,
    error_category: status === "provider_uncertain" ? "provider_timeout" : null,
    cancel_requested: false,
    steps: [],
    replayed: false,
  });
  workspaceMocks.getGenerationOutputs.mockResolvedValue({
    outputs:
      status === "partial_success"
        ? [
            {
              output_kind: "pptx",
              status: "succeeded",
              estimated_credits: 800,
              error_category: null,
              asset_id: "ppt-asset",
              asset_version: "sha256:ppt",
              quality_status: "passed",
              download_allowed: true,
              quality_report_schema_version: "presentation-quality-report.v1",
            },
            {
              output_kind: "xlsx",
              status: "failed",
              estimated_credits: 800,
              error_category: "quality_blocked",
              asset_id: "xlsx-asset",
              asset_version: "sha256:xlsx",
              quality_status: "blocked",
              download_allowed: false,
              quality_report_schema_version: "workbook-quality-report.v1",
            },
          ]
        : [],
  });
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
      { path: "/generations/:taskId", component: GenerationDetailView },
      { path: "/:pathMatch(.*)*", component: { template: "<div />" } },
    ],
  });
  await router.push("/generations/task-id");
  await router.isReady();
  const wrapper = mount(GenerationDetailView, {
    global: { plugins: [pinia, router] },
  });
  await flushPromises();
  return wrapper;
}

describe("Generation detail", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows partial success and only exposes validated downloads", async () => {
    const wrapper = await mountDetail();

    expect(wrapper.text()).toContain("部分完成");
    expect(wrapper.findAll("[data-testid='download-output']")).toHaveLength(1);
    expect(wrapper.text()).toContain("XLSX 未通过质量检查");
  });

  it("explains provider uncertainty without offering an unsafe retry", async () => {
    const wrapper = await mountDetail("provider_uncertain");

    expect(wrapper.text()).toContain("Provider 状态暂不确定");
    expect(wrapper.text()).toContain("系统不会自动重试或重复扣费");
    expect(wrapper.find("[data-testid='retry-generation']").exists()).toBe(false);
  });
});
