<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useRoute } from "vue-router";

import { ApiError } from "@/api/request";
import { workspaceApi } from "@/modules/workspace/api";
import type { WorkflowTask } from "@/modules/workspace/types";
import {
  isTerminalWorkflowTask,
  workflowTaskOutputLabel,
} from "@/modules/workspace/workflow-task-presentation";
import { useSessionStore } from "@/store/session";


const POLL_INTERVAL_MS = 3000;

const route = useRoute();
const session = useSessionStore();
const task = ref<WorkflowTask | null>(null);
const isLoading = ref(true);
const errorMessage = ref("");
let pollTimer: ReturnType<typeof setTimeout> | undefined;

const taskId = computed(() => String(route.params.taskId ?? ""));
const isTerminal = computed(
  () => Boolean(task.value && isTerminalWorkflowTask(task.value)),
);
const statusCopy = computed(() => {
  const status = task.value?.status;
  if (status === "failed") return "任务失败";
  if (status === "provider_uncertain") return "任务结果待确认";
  if (status === "succeeded") return "任务已完成";
  if (status === "partial_success") return "任务部分完成";
  if (status === "cancelled") return "任务已取消";
  if (status === "awaiting_confirmation") return "等待确认 Brief";
  if (status === "queued") return "任务排队中";
  return "任务进行中";
});

function requireToken() {
  if (!session.accessToken) throw new Error("登录状态已失效，请重新登录");
  return session.accessToken;
}

function readableError(error: unknown) {
  if (error instanceof ApiError || error instanceof Error) return error.message;
  return "无法加载任务，请稍后重试";
}

function clearPoll() {
  if (pollTimer !== undefined) {
    clearTimeout(pollTimer);
    pollTimer = undefined;
  }
}

function schedulePoll() {
  clearPoll();
  if (isTerminal.value) return;
  pollTimer = setTimeout(() => {
    pollTimer = undefined;
    void load(false);
  }, POLL_INTERVAL_MS);
}

async function load(showLoading = true) {
  if (showLoading) isLoading.value = task.value === null;
  errorMessage.value = "";
  try {
    task.value = await workspaceApi.getWorkflowTask(
      taskId.value,
      requireToken(),
    );
  } catch (error) {
    errorMessage.value = readableError(error);
  } finally {
    isLoading.value = false;
    schedulePoll();
  }
}

onMounted(load);
onBeforeUnmount(clearPoll);
</script>

<template>
  <section class="task-page" lang="zh-CN">
    <nav class="breadcrumb" aria-label="面包屑">
      <RouterLink to="/tasks">任务</RouterLink>
      <span>/</span>
      <span>{{ taskId }}</span>
    </nav>

    <div v-if="isLoading" class="state-panel" aria-live="polite">
      正在加载任务…
    </div>
    <div v-else-if="errorMessage && !task" class="state-panel state-panel--error">
      <p>{{ errorMessage }}</p>
      <button class="oa-button oa-button--secondary" type="button" @click="load()">
        重新加载
      </button>
    </div>

    <template v-else-if="task">
      <header class="task-heading">
        <p>工作流任务</p>
        <h1>{{ task.title }}</h1>
        <span class="status-pill">{{ statusCopy }}</span>
      </header>

      <section class="progress-card">
        <div class="progress-copy">
          <div>
            <span>当前进度</span>
            <strong>{{ task.note ?? statusCopy }}</strong>
          </div>
          <b class="oa-tabular">{{ task.progress }}%</b>
        </div>
        <div class="progress-track" :aria-label="`任务进度 ${task.progress}%`">
          <span :style="{ width: `${task.progress}%` }" />
        </div>
        <p>
          输出：
          {{ workflowTaskOutputLabel(task.output_kinds) }}
        </p>
      </section>

      <section v-if="task.failure_reason" class="failure-card" role="alert">
        <span>失败原因</span>
        <h2>{{ task.failure_reason }}</h2>
        <code>{{ task.failure_code }}</code>
        <p>失败记录已持久化。系统不会把 Provider 原始响应写入备注，也不会自动重复外部调用。</p>
      </section>

      <p v-if="errorMessage" class="oa-error" role="alert">{{ errorMessage }}</p>

      <section class="actions-card">
        <RouterLink
          v-if="task.brief_id && task.status === 'awaiting_confirmation'"
          class="oa-button oa-button--primary"
          data-testid="confirm-brief-link"
          :to="{
            name: 'brief-confirm',
            params: { briefId: task.brief_id },
          }"
        >
          查看并确认 Brief
        </RouterLink>
        <RouterLink
          v-if="task.generation_task_id"
          class="oa-button oa-button--primary"
          data-testid="generation-detail-link"
          :to="{
            name: 'generation-detail',
            params: { taskId: task.generation_task_id },
          }"
        >
          查看文件生成与下载
        </RouterLink>
        <button
          v-if="!isTerminal"
          class="oa-button oa-button--secondary"
          type="button"
          @click="load(false)"
        >
          刷新状态
        </button>
        <RouterLink class="oa-button oa-button--secondary" to="/tasks">
          返回任务列表
        </RouterLink>
      </section>

      <footer>
        <span>任务编号</span>
        <code>{{ task.task_id }}</code>
      </footer>
    </template>
  </section>
</template>

<style scoped>
.task-page {
  display: grid;
  width: min(100%, 960px);
  margin: 0 auto;
  padding: 32px clamp(18px, 5vw, 56px) 64px;
  gap: 22px;
}

.breadcrumb,
.actions-card {
  display: flex;
  align-items: center;
  gap: 12px;
}

.breadcrumb,
.breadcrumb a {
  color: var(--oa-muted);
  text-decoration: none;
}

.task-heading {
  display: grid;
  gap: 10px;
  padding: 24px 0 6px;
}

.task-heading p,
.task-heading h1 {
  margin: 0;
}

.task-heading p {
  color: var(--oa-accent);
  font-size: 13px;
  font-weight: 750;
}

.task-heading h1 {
  font-size: clamp(30px, 5vw, 46px);
}

.status-pill {
  width: fit-content;
  border-radius: 999px;
  padding: 6px 10px;
  color: #075985;
  background: #eaf3f8;
  font-size: 13px;
  font-weight: 750;
}

.progress-card,
.failure-card,
.actions-card,
.state-panel,
footer {
  border: 1px solid var(--oa-line);
  border-radius: 12px;
  padding: 24px;
  background: #fff;
}

.progress-copy {
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 20px;
}

.progress-copy div {
  display: grid;
  gap: 6px;
}

.progress-copy span,
.progress-card p,
footer span {
  color: var(--oa-muted);
}

.progress-copy b {
  font-size: 30px;
}

.progress-track {
  height: 8px;
  overflow: hidden;
  margin-top: 18px;
  border-radius: 999px;
  background: #e2e8f0;
}

.progress-track span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: var(--oa-accent);
}

.failure-card {
  border-color: #fecaca;
  background: #fff8f8;
}

.failure-card > span,
.failure-card p {
  color: #991b1b;
}

.failure-card h2 {
  margin: 8px 0;
  font-size: 21px;
}

.failure-card code,
footer code {
  overflow-wrap: anywhere;
}

.actions-card {
  flex-wrap: wrap;
}

.state-panel {
  text-align: center;
}

.state-panel--error {
  color: var(--oa-danger);
}

footer {
  display: grid;
  gap: 6px;
}

@media (max-width: 640px) {
  .progress-copy {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
