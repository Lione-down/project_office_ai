import type { WorkflowTask } from "./types";

const TERMINAL_WORKFLOW_TASK_STATUSES: ReadonlySet<string> = new Set([
  "succeeded",
  "partial_success",
  "failed",
  "provider_uncertain",
  "cancelled",
]);

const WORKFLOW_TASK_STATUS_LABELS: Readonly<Record<string, string>> = {
  queued: "排队中",
  running: "进行中",
  awaiting_confirmation: "等待确认",
  succeeded: "已完成",
  partial_success: "部分完成",
  failed: "失败",
  provider_uncertain: "结果待确认",
  cancelled: "已取消",
};

export function isTerminalWorkflowTask(task: Pick<WorkflowTask, "status">) {
  return TERMINAL_WORKFLOW_TASK_STATUSES.has(task.status);
}

export function workflowTaskStatusLabel(status: string) {
  return WORKFLOW_TASK_STATUS_LABELS[status] ?? status;
}

export function workflowTaskOutputLabel(
  outputKinds: WorkflowTask["output_kinds"],
) {
  return outputKinds.map((kind) => kind.toUpperCase()).join(" + ");
}

export function selectRecentWorkflowTasks(
  tasks: readonly WorkflowTask[],
  limit = 5,
) {
  return [...tasks]
    .sort(
      (left, right) =>
        Date.parse(right.created_at) - Date.parse(left.created_at),
    )
    .slice(0, limit);
}
