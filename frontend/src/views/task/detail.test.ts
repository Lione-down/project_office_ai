import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createMemoryHistory, createRouter } from "vue-router";

import { useSessionStore } from "@/store/session";

import WorkflowTaskDetailView from "./detail.vue";


const workspaceMocks = vi.hoisted(() => ({
  getWorkflowTask: vi.fn(),
}));

vi.mock("@/modules/workspace/api", () => ({
  workspaceApi: workspaceMocks,
}));

function task(overrides = {}) {
  return {
    task_id: "workflow-id",
    project_id: "project-id",
    brief_id: null,
    generation_task_id: null,
    title: "形成销售经营复盘",
    output_kinds: ["pptx", "xlsx"],
    stage: "brief_generating",
    status: "running",
    progress: 10,
    note: "正在整理 Brief",
    failure_code: null,
    failure_reason: null,
    estimated_credits: 0,
    settled_credits: 0,
    created_at: "2026-07-27T10:00:00Z",
    updated_at: "2026-07-27T10:01:00Z",
    replayed: false,
    ...overrides,
  };
}

async function mountDetail() {
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
        path: "/tasks/:taskId",
        name: "workflow-task-detail",
        component: WorkflowTaskDetailView,
      },
      {
        path: "/briefs/:briefId/confirm",
        name: "brief-confirm",
        component: { template: "<div />" },
      },
      {
        path: "/generations/:taskId",
        name: "generation-detail",
        component: { template: "<div />" },
      },
      {
        path: "/tasks",
        name: "tasks",
        component: { template: "<div />" },
      },
    ],
  });
  await router.push("/tasks/workflow-id");
  await router.isReady();
  const wrapper = mount(WorkflowTaskDetailView, {
    global: { plugins: [pinia, router] },
  });
  await flushPromises();
  return wrapper;
}

describe("Workflow task detail", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    workspaceMocks.getWorkflowTask.mockResolvedValue(task());
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("keeps a schema failure visible with its stable code and reason", async () => {
    workspaceMocks.getWorkflowTask.mockResolvedValue(
      task({
        stage: "brief_failed",
        status: "failed",
        progress: 100,
        note: "Brief 整理失败",
        failure_code: "brief_schema_invalid",
        failure_reason: "Structured Brief Schema 无效",
      }),
    );
    const wrapper = await mountDetail();

    expect(wrapper.text()).toContain("任务失败");
    expect(wrapper.text()).toContain("Brief 整理失败");
    expect(wrapper.text()).toContain("brief_schema_invalid");
    expect(wrapper.text()).toContain("Structured Brief Schema 无效");
    expect(workspaceMocks.getWorkflowTask).toHaveBeenCalledTimes(1);
  });

  it("polls a running task and exposes Brief confirmation when ready", async () => {
    vi.useFakeTimers();
    workspaceMocks.getWorkflowTask
      .mockResolvedValueOnce(task())
      .mockResolvedValueOnce(
        task({
          brief_id: "brief-id",
          stage: "awaiting_confirmation",
          status: "awaiting_confirmation",
          progress: 30,
          note: "Brief 已就绪，等待确认",
        }),
      );
    const wrapper = await mountDetail();

    expect(wrapper.text()).toContain("正在整理 Brief");
    await vi.advanceTimersByTimeAsync(3000);
    await flushPromises();

    expect(workspaceMocks.getWorkflowTask).toHaveBeenCalledTimes(2);
    expect(wrapper.text()).toContain("Brief 已就绪，等待确认");
    expect(wrapper.get("[data-testid='confirm-brief-link']").attributes("href")).toBe(
      "/briefs/brief-id/confirm",
    );
  });
});
