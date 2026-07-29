import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useSessionStore } from "@/store/session";

import UserResourceView from "./resource.vue";

const workspaceMocks = vi.hoisted(() => ({
  loadOptions: vi.fn(),
  getCreditBalance: vi.fn(),
  getCreditLedger: vi.fn(),
  listWorkflowTasks: vi.fn(),
  listTemplates: vi.fn(),
  getTemplate: vi.fn(),
}));

vi.mock("@/modules/workspace/api", () => ({
  workspaceApi: workspaceMocks,
}));

async function mountResource(
  section: "tasks" | "files" | "templates" | "term-libraries" | "credits",
) {
  const pinia = createPinia();
  setActivePinia(pinia);
  useSessionStore().setTokens({
    access_token: "access",
    refresh_token: "refresh",
    token_type: "bearer",
  });
  const wrapper = mount(UserResourceView, {
    props: { section },
    global: {
      plugins: [pinia],
      stubs: { RouterLink: { template: "<a><slot /></a>" } },
    },
  });
  await flushPromises();
  return wrapper;
}

describe("User resource views", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    workspaceMocks.loadOptions.mockResolvedValue({
      projects: [],
      assets: [],
      skills: [],
      models: [],
      termLibraries: [],
    });
    workspaceMocks.getCreditBalance.mockResolvedValue({ balance: 8420 });
    workspaceMocks.getCreditLedger.mockResolvedValue({ entries: [] });
    workspaceMocks.listWorkflowTasks.mockResolvedValue([]);
    workspaceMocks.listTemplates.mockResolvedValue([
      {
        template_code: "ppt.executive-blue.v1",
        version: "1.0.0",
        checksum: "a".repeat(64),
        name: "高管钢蓝",
        category: "management",
        style_keywords: ["克制", "专业"],
        use_cases: ["管理层经营汇报"],
        compatible_skills: [
          "ppt.sales-business-review.v1",
          "ppt.knowledge-education.v1",
        ],
        cover_url: "/template-previews/ppt.executive-blue.v1/cover.svg",
        representative_urls: [
          "/template-previews/ppt.executive-blue.v1/content.svg",
        ],
      },
      {
        template_code: "ppt.operating-review.v1",
        version: "1.0.0",
        checksum: "b".repeat(64),
        name: "经营复盘",
        category: "review",
        style_keywords: ["行动", "复盘"],
        use_cases: ["经营复盘"],
        compatible_skills: ["ppt.sales-business-review.v1"],
        cover_url: "/template-previews/ppt.operating-review.v1/cover.svg",
        representative_urls: [
          "/template-previews/ppt.operating-review.v1/content.svg",
        ],
      },
      {
        template_code: "ppt.data-story.v1",
        version: "1.0.0",
        checksum: "c".repeat(64),
        name: "数据叙事",
        category: "data-story",
        style_keywords: ["数据", "叙事"],
        use_cases: ["指标分析"],
        compatible_skills: [
          "ppt.sales-business-review.v1",
          "ppt.knowledge-education.v1",
        ],
        cover_url: "/template-previews/ppt.data-story.v1/cover.svg",
        representative_urls: [
          "/template-previews/ppt.data-story.v1/content.svg",
        ],
      },
    ]);
    workspaceMocks.getTemplate.mockResolvedValue({
      template_code: "ppt.executive-blue.v1",
      version: "1.0.0",
      checksum: "a".repeat(64),
      name: "高管钢蓝",
      category: "management",
      description: "原创管理汇报模板",
      style_keywords: ["克制", "专业"],
      use_cases: ["管理层经营汇报"],
      colors: ["#F5F8FC", "#123B6D"],
      fonts: ["Microsoft YaHei"],
      layouts: ["title", "content", "section", "closing"],
      compatible_skills: [
        "ppt.sales-business-review.v1",
        "ppt.knowledge-education.v1",
      ],
      cover_url: "/template-previews/ppt.executive-blue.v1/cover.svg",
      representative_urls: [
        "/template-previews/ppt.executive-blue.v1/representative.svg",
      ],
      source: {
        kind: "system_original",
        license: "Office AI Original",
        attribution: "Office AI Design System",
      },
    });
  });

  it("opens template details with renderer metadata and original source", async () => {
    const wrapper = await mountResource("templates");

    await wrapper
      .get("[data-testid='template-detail-ppt.executive-blue.v1']")
      .trigger("click");
    await flushPromises();

    expect(workspaceMocks.getTemplate).toHaveBeenCalledWith(
      "ppt.executive-blue.v1",
      "1.0.0",
      "access",
    );
    expect(wrapper.get("[data-testid='template-detail']").text()).toContain(
      "Office AI Original",
    );
    expect(wrapper.get("[data-testid='template-detail']").text()).toContain(
      "title · content · section · closing",
    );
    expect(
      wrapper
        .get("[data-testid='template-representative']")
        .attributes("src"),
    ).toBe(
      "/template-previews/ppt.executive-blue.v1/representative.svg",
    );
  });

  it("shows real owner-scoped file metadata and processing state", async () => {
    workspaceMocks.loadOptions.mockResolvedValue({
      projects: [],
      assets: [
        {
          asset_id: "asset-id",
          original_filename: "华东销售数据.xlsx",
          file_category: "xlsx",
          byte_size: 4096,
          processing_status: "ready",
          manifest_status: "ready",
        },
      ],
      skills: [],
      models: [],
      termLibraries: [],
    });
    const wrapper = await mountResource("files");

    expect(wrapper.text()).toContain("华东销售数据.xlsx");
    expect(wrapper.text()).toContain("可用于生成");
  });

  it("loads the certified PPT catalog with original previews and version metadata", async () => {
    const wrapper = await mountResource("templates");

    expect(workspaceMocks.listTemplates).toHaveBeenCalledWith("access");
    expect(wrapper.findAll("[data-testid='system-template']")).toHaveLength(3);
    expect(wrapper.text()).toContain("高管钢蓝");
    expect(wrapper.text()).toContain("v1.0.0");
    expect(wrapper.text()).toContain("管理层经营汇报");
    expect(
      wrapper
        .find("[data-testid='system-template'] img")
        .attributes("src"),
    ).toBe("/template-previews/ppt.executive-blue.v1/cover.svg");
    expect(
      wrapper.findAll("[data-testid='system-workbook-template']"),
    ).toHaveLength(2);
    expect(wrapper.text()).toContain("分析看板");
    expect(wrapper.text()).toContain("Excel 模板");
    expect(wrapper.text()).not.toContain("上传模板");
  });

  it("shows balance and immutable ledger entries", async () => {
    workspaceMocks.getCreditLedger.mockResolvedValue({
      entries: [
        {
          entry_id: "entry-id",
          task_id: "task-id",
          entry_type: "generation_finalize",
          amount: 0,
          balance_after: 8420,
          created_at: "2026-07-23T00:00:00Z",
        },
      ],
    });
    const wrapper = await mountResource("credits");

    expect(wrapper.text()).toContain("8,420");
    expect(wrapper.text()).toContain("生成结算");
    expect(wrapper.text()).toContain("流水只追加");
  });

  it("shows durable task progress, notes, and failure reasons", async () => {
    workspaceMocks.listWorkflowTasks.mockResolvedValue([
      {
        task_id: "workflow-id",
        project_id: "project-id",
        brief_id: null,
        generation_task_id: null,
        title: "形成销售经营复盘",
        output_kinds: ["pptx", "xlsx"],
        stage: "brief_failed",
        status: "failed",
        progress: 100,
        note: "Brief 整理失败",
        failure_code: "brief_schema_invalid",
        failure_reason: "Structured Brief Schema 无效",
        estimated_credits: 0,
        settled_credits: 0,
        created_at: "2026-07-27T10:00:00Z",
        updated_at: "2026-07-27T10:02:00Z",
        replayed: false,
      },
    ]);
    const wrapper = await mountResource("tasks");

    expect(workspaceMocks.listWorkflowTasks).toHaveBeenCalledWith("access");
    expect(wrapper.findAll("tbody tr")).toHaveLength(1);
    expect(wrapper.text()).toContain("形成销售经营复盘");
    expect(wrapper.text()).toContain("PPTX + XLSX");
    expect(wrapper.text()).toContain("失败");
    expect(wrapper.text()).toContain("100%");
    expect(wrapper.text()).toContain("Brief 整理失败");
    expect(wrapper.text()).toContain("Structured Brief Schema 无效");
    expect(wrapper.text()).not.toContain("任务列表接口尚未交付");
  });
});
