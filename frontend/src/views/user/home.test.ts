import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createMemoryHistory, createRouter } from "vue-router";

import type { WorkflowTask } from "@/modules/workspace/types";
import { useSessionStore } from "@/store/session";

import HomeView from "./home.vue";

const workspaceMocks = vi.hoisted(() => ({
  listWorkflowTasks: vi.fn(),
}));

vi.mock("@/modules/workspace/api", () => ({
  workspaceApi: workspaceMocks,
}));

function workflowTask(
  overrides: Partial<WorkflowTask> & Pick<WorkflowTask, "task_id" | "title">,
): WorkflowTask {
  const { task_id, title, ...remainingOverrides } = overrides;
  return {
    task_id,
    project_id: "project-id",
    brief_id: null,
    generation_task_id: null,
    title,
    output_kinds: ["pptx"],
    stage: "brief_generating",
    status: "running",
    progress: 37,
    note: null,
    failure_code: null,
    failure_reason: null,
    estimated_credits: 800,
    settled_credits: 0,
    created_at: "2026-07-29T10:00:00Z",
    updated_at: "2026-07-29T10:01:00Z",
    replayed: false,
    ...remainingOverrides,
  };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((promiseResolve, promiseReject) => {
    resolve = promiseResolve;
    reject = promiseReject;
  });
  return { promise, resolve, reject };
}

async function mountHome() {
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
      { path: "/", name: "home", component: HomeView },
      {
        path: "/workflow/new",
        name: "workflow-new",
        component: { template: "<div />" },
      },
      {
        path: "/tasks",
        name: "tasks",
        component: { template: "<div />" },
      },
      {
        path: "/tasks/:taskId",
        name: "workflow-task-detail",
        component: { template: "<div />" },
      },
      { path: "/:pathMatch(.*)*", component: { template: "<div />" } },
    ],
  });
  await router.push("/");
  await router.isReady();
  const wrapper = mount(HomeView, {
    global: { plugins: [pinia, router] },
  });
  return { wrapper, router };
}

describe("User home", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    workspaceMocks.listWorkflowTasks.mockResolvedValue([]);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("offers the three approved output choices with one filled primary action", async () => {
    const { wrapper } = await mountHome();

    expect(wrapper.findAll("[data-testid='workflow-choice']")).toHaveLength(3);
    expect(wrapper.findAll(".oa-button--primary")).toHaveLength(1);
    expect(wrapper.text()).toContain("制作销售汇报");
    expect(wrapper.text()).toContain("分析销售数据");
    expect(wrapper.text()).toContain("两项一起完成");
  });

  it("carries the selected output mode into the new workflow", async () => {
    const { wrapper, router } = await mountHome();

    await wrapper
      .findAll("[data-testid='workflow-choice']")[2]
      .trigger("click");
    await wrapper.get("[data-testid='continue-workflow']").trigger("click");
    await flushPromises();

    expect(router.currentRoute.value).toMatchObject({
      name: "workflow-new",
      query: { mode: "combined" },
    });
  });

  it("distinguishes initial loading from an empty recent-task result", async () => {
    const request = deferred<WorkflowTask[]>();
    workspaceMocks.listWorkflowTasks.mockReturnValueOnce(request.promise);
    const { wrapper } = await mountHome();

    expect(wrapper.get("[data-testid='recent-loading']").text()).toContain(
      "正在加载最近任务",
    );

    request.resolve([]);
    await flushPromises();

    expect(workspaceMocks.listWorkflowTasks).toHaveBeenCalledWith("access");
    expect(wrapper.find("[data-testid='recent-loading']").exists()).toBe(false);
    expect(wrapper.get("[data-testid='recent-empty']").text()).toContain(
      "还没有任务",
    );
  });

  it("shows the newest five owner-scoped tasks with authoritative status and progress", async () => {
    workspaceMocks.listWorkflowTasks.mockResolvedValue([
      workflowTask({
        task_id: "task-2",
        title: "第二新任务",
        output_kinds: ["xlsx"],
        status: "awaiting_confirmation",
        progress: 52,
        created_at: "2026-07-29T12:00:00Z",
        updated_at: "2026-07-29T12:01:00Z",
      }),
      workflowTask({
        task_id: "task-6",
        title: "最旧任务不应显示",
        created_at: "2026-07-29T08:00:00Z",
      }),
      workflowTask({
        task_id: "task-1",
        title: "最新任务",
        output_kinds: ["pptx", "xlsx"],
        status: "running",
        progress: 37,
        created_at: "2026-07-29T13:00:00Z",
        updated_at: "2026-07-29T13:02:00Z",
      }),
      workflowTask({
        task_id: "task-4",
        title: "第四新任务",
        status: "failed",
        progress: 100,
        failure_code: "internal_failure_code",
        failure_reason: "C:\\private\\unsafe-provider-detail",
        created_at: "2026-07-29T10:00:00Z",
      }),
      workflowTask({
        task_id: "task-5",
        title: "第五新任务",
        status: "succeeded",
        progress: 100,
        created_at: "2026-07-29T09:00:00Z",
      }),
      workflowTask({
        task_id: "task-3",
        title: "第三新任务",
        status: "queued",
        progress: 0,
        created_at: "2026-07-29T11:00:00Z",
      }),
    ]);
    const { wrapper } = await mountHome();
    await flushPromises();

    const cards = wrapper.findAll("[data-testid='recent-task']");
    expect(cards).toHaveLength(5);
    expect(cards.map((card) => card.get("h3").text())).toEqual([
      "最新任务",
      "第二新任务",
      "第三新任务",
      "第四新任务",
      "第五新任务",
    ]);
    expect(cards[0].text()).toContain("PPTX + XLSX");
    expect(cards[0].text()).toContain("进行中");
    expect(cards[0].text()).toContain("37%");
    expect(cards[0].get("progress").attributes("value")).toBe("37");
    expect(cards[0].get("time").attributes("datetime")).toBe(
      "2026-07-29T13:02:00Z",
    );
    expect(cards[0].get("a").attributes("href")).toBe("/tasks/task-1");
    expect(wrapper.text()).not.toContain("最旧任务不应显示");
    expect(wrapper.text()).not.toContain("internal_failure_code");
    expect(wrapper.text()).not.toContain("unsafe-provider-detail");
  });

  it("shows a safe failure state and retries the owner-scoped list request", async () => {
    workspaceMocks.listWorkflowTasks
      .mockRejectedValueOnce(new Error("C:\\private\\provider-response.json"))
      .mockResolvedValueOnce([
        workflowTask({
          task_id: "retry-task",
          title: "重试后任务",
          status: "succeeded",
          progress: 100,
        }),
      ]);
    const { wrapper } = await mountHome();
    await flushPromises();

    const failure = wrapper.get("[data-testid='recent-error']");
    expect(failure.text()).toContain("最近任务加载失败");
    expect(failure.text()).not.toContain("provider-response.json");

    await failure.get("button").trigger("click");
    await flushPromises();

    expect(workspaceMocks.listWorkflowTasks).toHaveBeenCalledTimes(2);
    expect(wrapper.text()).toContain("重试后任务");
    expect(wrapper.find("[data-testid='recent-error']").exists()).toBe(false);
  });

  it("polls only while a recent task is non-terminal and stops after all are terminal", async () => {
    vi.useFakeTimers();
    workspaceMocks.listWorkflowTasks
      .mockResolvedValueOnce([
        workflowTask({ task_id: "active-task", title: "进行中任务" }),
      ])
      .mockResolvedValueOnce([
        workflowTask({
          task_id: "active-task",
          title: "已完成任务",
          status: "succeeded",
          progress: 100,
        }),
      ]);
    const { wrapper } = await mountHome();
    await flushPromises();

    expect(workspaceMocks.listWorkflowTasks).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(3000);
    await flushPromises();
    expect(workspaceMocks.listWorkflowTasks).toHaveBeenCalledTimes(2);
    expect(wrapper.text()).toContain("已完成任务");

    await vi.advanceTimersByTimeAsync(6000);
    expect(workspaceMocks.listWorkflowTasks).toHaveBeenCalledTimes(2);
  });

  it("clears pending task polling when the home view unmounts", async () => {
    vi.useFakeTimers();
    workspaceMocks.listWorkflowTasks.mockResolvedValue([
      workflowTask({ task_id: "active-task", title: "进行中任务" }),
    ]);
    const { wrapper } = await mountHome();
    await flushPromises();

    wrapper.unmount();
    await vi.advanceTimersByTimeAsync(6000);

    expect(workspaceMocks.listWorkflowTasks).toHaveBeenCalledTimes(1);
  });
});
