import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createMemoryHistory, createRouter } from "vue-router";

import { useSessionStore } from "@/store/session";

import BriefConfirmView from "./confirm.vue";


const apiMocks = vi.hoisted(() => ({
  getBrief: vi.fn(),
  reviseBrief: vi.fn(),
  preflight: vi.fn(),
  confirm: vi.fn(),
}));

const workspaceMocks = vi.hoisted(() => ({
  createGeneration: vi.fn(),
}));

vi.mock("@/modules/briefs/api", () => ({
  briefApi: apiMocks,
}));

vi.mock("@/modules/workspace/api", () => ({
  workspaceApi: workspaceMocks,
}));

const brief = {
  brief_id: "019f4000-0000-7000-8000-000000000030",
  brief_group_id: "019f4000-0000-7000-8000-000000000007",
  revision: 1,
  status: "draft",
  content: {
    goal: "形成月度销售经营复盘",
    audience: "销售管理层",
    source_asset_versions: [{ asset_id: "asset-id", asset_version: "sha256:test" }],
    must_include: [{ content: "销售额", source: "user", evidence_ids: [] }],
  },
  content_checksum: "checksum",
  source_snapshot: {},
  estimated_credits: null,
  confirmed_at: null,
};

function preflight(hasBlockers = false) {
  return {
    brief_id: brief.brief_id,
    brief_group_id: brief.brief_group_id,
    revision: 1,
    status: hasBlockers ? "needs_resolution" : "preflight",
    conflicts: hasBlockers
      ? [
          {
            code: "unit_unknown",
            level: "blocking",
            message: "请为数值补充明确单位后继续",
            evidence_ids: ["e-1"],
          },
        ]
      : [
          {
            code: "narrative_low_confidence",
            level: "needs_confirmation",
            message: "请确认经营建议表述",
            evidence_ids: ["e-2"],
          },
        ],
    outputs: [
      {
        skill_code: "ppt.sales-business-review.v1",
        kind: "pptx",
        title: "销售经营汇报",
        template_code: "ppt.executive-blue.v1",
        template_version: "1.0.0",
        estimated_credits: 800,
      },
    ],
    estimated_credits: 800,
    has_blockers: hasBlockers,
    confirmed_at: null,
  };
}

async function mountView(hasBlockers = false) {
  const pinia = createPinia();
  setActivePinia(pinia);
  const session = useSessionStore();
  session.setAccessToken("access-token");
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      {
        path: "/briefs/:briefId/confirm",
        component: BriefConfirmView,
      },
      {
        path: "/generations/:taskId",
        name: "generation-detail",
        component: { template: "<p>任务详情</p>" },
      },
    ],
  });
  apiMocks.getBrief.mockResolvedValue(brief);
  apiMocks.preflight.mockResolvedValue(preflight(hasBlockers));
  await router.push(`/briefs/${brief.brief_id}/confirm`);
  await router.isReady();
  const wrapper = mount(BriefConfirmView, {
    global: { plugins: [pinia, router] },
  });
  await flushPromises();
  return wrapper;
}

describe("Brief confirmation view", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows actionable blockers and disables the single primary action", async () => {
    const wrapper = await mountView(true);

    expect(wrapper.text()).toContain("确认后进入生成队列");
    expect(wrapper.text()).toContain("高管钢蓝 · v1.0.0");
    expect(wrapper.text()).not.toContain("ppt.executive-blue.v1 @ 1.0.0");
    expect(wrapper.text()).toContain("请为数值补充明确单位后继续");
    expect(wrapper.get("[data-testid='estimated-credits']").text()).toContain("800");
    expect(wrapper.get("[data-testid='confirm-brief']").attributes("disabled")).toBeDefined();
  });

  it("saves explicit unit resolutions as a new revision", async () => {
    const revisedBriefId = "019f4000-0000-7000-8000-000000000032";
    apiMocks.reviseBrief.mockResolvedValue({
      ...brief,
      brief_id: revisedBriefId,
      revision: 2,
    });
    const wrapper = await mountView(true);

    await wrapper.get("[data-testid='unit-resolution-0']").setValue("CNY_10K");
    await wrapper.get("[data-testid='save-brief']").trigger("click");
    await flushPromises();

    expect(apiMocks.reviseBrief).toHaveBeenCalledWith(
      brief.brief_id,
      {
        expected_revision: 1,
        goal: "形成月度销售经营复盘",
        audience: "销售管理层",
        resolutions: [
          {
            code: "unit_unknown",
            evidence_ids: ["e-1"],
            action: "assign_unit",
            value: "CNY_10K",
          },
        ],
      },
      "access-token",
    );
    expect(apiMocks.preflight).toHaveBeenLastCalledWith(
      revisedBriefId,
      "access-token",
    );
  });

  it("confirms the accepted estimate when preflight is clean", async () => {
    apiMocks.confirm.mockResolvedValue({ ...preflight(), status: "queued" });
    workspaceMocks.createGeneration.mockResolvedValue({
      task_id: "generation-id",
    });
    const wrapper = await mountView(false);

    expect(wrapper.text()).toContain("请确认经营建议表述");
    await wrapper.get("[data-testid='confirm-brief']").trigger("click");
    await flushPromises();

    expect(apiMocks.confirm).toHaveBeenCalledWith(
      brief.brief_id,
      800,
      "access-token",
    );
    expect(workspaceMocks.createGeneration).toHaveBeenCalledWith(
      brief.brief_id,
      expect.any(String),
      "access-token",
    );
    expect(wrapper.findComponent({ name: "RouterView" }).exists()).toBe(false);
    expect(wrapper.vm.$router.currentRoute.value.name).toBe("generation-detail");
    expect(wrapper.vm.$router.currentRoute.value.params.taskId).toBe(
      "generation-id",
    );
  });

  it("saves a goal edit as the next immutable revision", async () => {
    const revisedBriefId = "019f4000-0000-7000-8000-000000000031";
    apiMocks.reviseBrief.mockResolvedValue({
      ...brief,
      brief_id: revisedBriefId,
      revision: 2,
      content: { ...brief.content, goal: "形成董事会季度销售复盘" },
    });
    const wrapper = await mountView(false);

    await wrapper.get("[data-testid='brief-goal']").setValue("形成董事会季度销售复盘");
    await wrapper.get("[data-testid='save-brief']").trigger("click");
    await flushPromises();

    expect(apiMocks.reviseBrief).toHaveBeenCalledWith(
      brief.brief_id,
      {
        expected_revision: 1,
        goal: "形成董事会季度销售复盘",
        audience: "销售管理层",
      },
      "access-token",
    );
    expect(apiMocks.preflight).toHaveBeenLastCalledWith(
      revisedBriefId,
      "access-token",
    );
  });
});
