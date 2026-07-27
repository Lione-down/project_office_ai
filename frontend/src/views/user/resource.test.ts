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

  it("lists the five certified system templates without upload controls", async () => {
    const wrapper = await mountResource("templates");

    expect(wrapper.findAll("[data-testid='system-template']")).toHaveLength(5);
    expect(wrapper.text()).toContain("高管钢蓝");
    expect(wrapper.text()).toContain("分析看板");
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
