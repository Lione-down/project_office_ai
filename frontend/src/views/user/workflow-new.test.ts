import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createMemoryHistory, createRouter } from "vue-router";

import { useSessionStore } from "@/store/session";
import type { WorkspaceOptions } from "@/modules/workspace/types";

import WorkflowNewView from "./workflow-new.vue";

const workspaceMocks = vi.hoisted(() => ({
  loadOptions: vi.fn(),
  uploadAsset: vi.fn(),
  generateBrief: vi.fn(),
}));

vi.mock("@/modules/workspace/api", () => ({
  workspaceApi: workspaceMocks,
}));

const options: WorkspaceOptions = {
  projects: [
    {
      project_id: "project-id",
      name: "华东区域",
      is_default: true,
      is_archived: false,
      created_at: "2026-07-23T00:00:00Z",
      updated_at: "2026-07-23T00:00:00Z",
    },
  ],
  assets: [
    {
      asset_id: "asset-id",
      project_id: "project-id",
      original_filename: "华东销售数据.xlsx",
      file_category: "xlsx",
      mime_type: "application/octet-stream",
      byte_size: 2048,
      sha256: "sha256",
      processing_status: "ready",
      parser_name: "xlsx",
      parser_version: "1",
      processing_warnings: [],
      processing_error_code: null,
      processing_error_message: null,
      manifest_status: "ready",
      manifest_schema_version: "evidence-manifest.v1",
      evidence_engine_version: "1",
      evidence_warning_count: 0,
      evidence_blocker_count: 0,
      quality_status: null,
      created_at: "2026-07-23T00:00:00Z",
      updated_at: "2026-07-23T00:00:00Z",
    },
  ],
  skills: [
    {
      skill_code: "ppt.sales-business-review.v1",
      version: "1.0.0",
      display_name: "销售经营汇报",
      description: "生成 PPTX",
      output_kind: "pptx",
      status: "published",
    },
    {
      skill_code: "excel.sales-analysis-dashboard.v1",
      version: "1.0.0",
      display_name: "销售数据分析与经营看板",
      description: "生成 XLSX",
      output_kind: "xlsx",
      status: "published",
    },
  ],
  models: [
    {
      model_id: "model-id",
      provider_id: "provider-id",
      credential_id: "credential-id",
      model_code: "agnes-2.0-flash",
      display_name: "Agnes 2.0 Flash",
      capabilities: {},
      context_window: 256000,
      max_output_tokens: 16000,
      user_visible: true,
      is_recommended: true,
      credit_multiplier: "1.0000",
      allowed_skills: [
        "ppt.sales-business-review.v1",
        "excel.sales-analysis-dashboard.v1",
      ],
      status: "active",
    },
  ],
  termLibraries: [],
};

async function mountWorkflow(loadedOptions = options) {
  workspaceMocks.loadOptions.mockResolvedValue(loadedOptions);
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
        path: "/workflow/new",
        name: "workflow-new",
        component: WorkflowNewView,
      },
      {
        path: "/briefs/:briefId/confirm",
        name: "brief-confirm",
        component: { template: "<div />" },
      },
      { path: "/:pathMatch(.*)*", component: { template: "<div />" } },
    ],
  });
  await router.push("/workflow/new?mode=combined");
  await router.isReady();
  const wrapper = mount(WorkflowNewView, {
    global: { plugins: [pinia, router] },
  });
  await flushPromises();
  return { wrapper, router };
}

describe("New workflow", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("creates a combined Brief from ready owner-scoped selections", async () => {
    workspaceMocks.generateBrief.mockResolvedValue({ brief_id: "brief-id" });
    const { wrapper, router } = await mountWorkflow();

    await wrapper.get("[data-testid='workflow-submit']").trigger("submit");
    await flushPromises();

    expect(workspaceMocks.generateBrief).toHaveBeenCalledWith(
      expect.objectContaining({
        project_id: "project-id",
        asset_ids: ["asset-id"],
        skill_codes: [
          "ppt.sales-business-review.v1",
          "excel.sales-analysis-dashboard.v1",
        ],
        model_id: "model-id",
      }),
      "access",
    );
    expect(router.currentRoute.value).toMatchObject({
      name: "brief-confirm",
      params: { briefId: "brief-id" },
    });
  });

  it("blocks submission when the selected material is not ready", async () => {
    const pendingOptions = {
      ...options,
      assets: [{ ...options.assets[0], processing_status: "quarantined" }],
    };
    const { wrapper } = await mountWorkflow(pendingOptions);

    expect(wrapper.text()).toContain("材料完成安全处理后才能继续");
    expect(
      wrapper.get("[data-testid='workflow-primary-action']").attributes("disabled"),
    ).toBeDefined();
  });

  it("keeps the first-material upload available when no project exists", async () => {
    const { wrapper } = await mountWorkflow({
      ...options,
      projects: [],
      assets: [],
    });

    expect(wrapper.text()).toContain("上传首份材料后自动创建默认项目");
    expect(
      wrapper.get("[data-testid='workflow-file-input']").attributes("disabled"),
    ).toBeUndefined();
  });

  it("uploads the first material without an explicit project", async () => {
    workspaceMocks.uploadAsset.mockResolvedValue({ asset_id: "asset-id" });
    const { wrapper } = await mountWorkflow({
      ...options,
      projects: [],
      assets: [],
    });
    const input = wrapper.get("[data-testid='workflow-file-input']");
    const file = new File(["sales"], "sales.csv", { type: "text/csv" });
    Object.defineProperty(input.element, "files", {
      configurable: true,
      value: [file],
    });

    await input.trigger("change");
    await flushPromises();

    expect(workspaceMocks.uploadAsset).toHaveBeenCalledWith(
      file,
      undefined,
      expect.any(String),
      "access",
    );
  });

  it("pins selected term library versions into the immutable Brief", async () => {
    workspaceMocks.generateBrief.mockResolvedValue({ brief_id: "brief-id" });
    const loadedOptions = {
      ...options,
      termLibraries: [
        {
          library_id: "library-id",
          version: 3,
          name: "销售口径",
          status: "active",
        },
      ],
    };
    const { wrapper } = await mountWorkflow(loadedOptions);

    await wrapper.get("[data-testid='term-library-version']").setValue(true);
    await wrapper.get("[data-testid='workflow-submit']").trigger("submit");
    await flushPromises();

    expect(workspaceMocks.generateBrief).toHaveBeenCalledWith(
      expect.objectContaining({
        term_library_versions: [
          { library_id: "library-id", version: 3 },
        ],
      }),
      "access",
    );
  });
});
