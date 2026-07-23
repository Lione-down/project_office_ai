import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useSessionStore } from "@/store/session";

import UserResourceView from "./resource.vue";

const workspaceMocks = vi.hoisted(() => ({
  loadOptions: vi.fn(),
  getCreditBalance: vi.fn(),
  getCreditLedger: vi.fn(),
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

  it("does not invent task history when the backend has no task list endpoint", async () => {
    const wrapper = await mountResource("tasks");

    expect(wrapper.text()).toContain("任务列表接口尚未交付");
    expect(wrapper.findAll("tbody tr")).toHaveLength(0);
  });
});
