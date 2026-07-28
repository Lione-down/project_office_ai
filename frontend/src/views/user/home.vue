<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useRouter } from "vue-router";

import { workspaceApi } from "@/modules/workspace/api";
import type { WorkflowTask } from "@/modules/workspace/types";
import {
  isTerminalWorkflowTask,
  selectRecentWorkflowTasks,
  workflowTaskOutputLabel,
  workflowTaskStatusLabel,
} from "@/modules/workspace/workflow-task-presentation";
import { useSessionStore } from "@/store/session";

type WorkflowMode = "pptx" | "xlsx" | "combined";

const RECENT_TASK_LIMIT = 5;
const TASK_POLL_INTERVAL_MS = 3000;

const router = useRouter();
const session = useSessionStore();
const selectedMode = ref<WorkflowMode>("combined");
const workflowTasks = ref<WorkflowTask[]>([]);
const isRecentLoading = ref(true);
const hasRecentError = ref(false);
const recentTasks = computed(() =>
  selectRecentWorkflowTasks(workflowTasks.value, RECENT_TASK_LIMIT),
);
let taskPollTimer: ReturnType<typeof setTimeout> | undefined;
let latestRequest = 0;
let isActive = false;

const choices: Array<{
  mode: WorkflowMode;
  title: string;
  description: string;
  fileLabel: string;
}> = [
  {
    mode: "pptx",
    title: "制作销售汇报",
    description: "生成可下载的 PPTX",
    fileLabel: "PPTX",
  },
  {
    mode: "xlsx",
    title: "分析销售数据",
    description: "生成分析表与经营看板",
    fileLabel: "XLSX",
  },
  {
    mode: "combined",
    title: "两项一起完成",
    description: "使用同一份材料生成 PPTX 和 XLSX",
    fileLabel: "PPTX + XLSX",
  },
];

function requireToken() {
  if (!session.accessToken) throw new Error("登录状态已失效");
  return session.accessToken;
}

function clearTaskPoll() {
  if (taskPollTimer !== undefined) {
    clearTimeout(taskPollTimer);
    taskPollTimer = undefined;
  }
}

function scheduleTaskPoll() {
  clearTaskPoll();
  if (
    !isActive ||
    hasRecentError.value ||
    !workflowTasks.value.some((task) => !isTerminalWorkflowTask(task))
  ) {
    return;
  }
  taskPollTimer = setTimeout(() => {
    taskPollTimer = undefined;
    void loadRecentTasks(false);
  }, TASK_POLL_INTERVAL_MS);
}

async function loadRecentTasks(showLoading = true) {
  clearTaskPoll();
  const request = ++latestRequest;
  if (showLoading) isRecentLoading.value = true;
  hasRecentError.value = false;
  try {
    const result = await workspaceApi.listWorkflowTasks(requireToken());
    if (!isActive || request !== latestRequest) return;
    workflowTasks.value = result;
  } catch {
    if (!isActive || request !== latestRequest) return;
    hasRecentError.value = true;
  } finally {
    if (!isActive || request !== latestRequest) return;
    isRecentLoading.value = false;
    scheduleTaskPoll();
  }
}

function formatUpdatedAt(value: string) {
  return new Intl.DateTimeFormat("zh-CN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

async function continueWorkflow() {
  await router.push({
    name: "workflow-new",
    query: { mode: selectedMode.value },
  });
}

onMounted(() => {
  isActive = true;
  void loadRecentTasks();
});

onBeforeUnmount(() => {
  isActive = false;
  latestRequest += 1;
  clearTaskPoll();
});
</script>

<template>
  <section class="home-page" lang="zh-CN">
    <header>
      <p>Office AI 工作台</p>
      <h1>今天想完成什么？</h1>
      <span>选择一项工作，剩下的交给系统。</span>
    </header>

    <div class="choice-grid" role="radiogroup" aria-label="选择输出">
      <button
        v-for="choice in choices"
        :key="choice.mode"
        type="button"
        class="workflow-choice"
        :class="{ selected: selectedMode === choice.mode }"
        data-testid="workflow-choice"
        role="radio"
        :aria-checked="selectedMode === choice.mode"
        @click="selectedMode = choice.mode"
      >
        <span class="workflow-choice__kind">{{ choice.fileLabel }}</span>
        <strong>{{ choice.title }}</strong>
        <small>{{ choice.description }}</small>
        <span v-if="selectedMode === choice.mode" class="selected-mark">已选择</span>
      </button>
    </div>

    <button
      type="button"
      class="oa-button oa-button--primary continue-button"
      data-testid="continue-workflow"
      @click="continueWorkflow"
    >
      继续
    </button>

    <section class="recent-section" aria-labelledby="recent-title">
      <div class="recent-heading">
        <h2 id="recent-title">最近任务</h2>
        <RouterLink to="/tasks">查看全部</RouterLink>
      </div>

      <div
        v-if="isRecentLoading"
        class="recent-state"
        data-testid="recent-loading"
        role="status"
        aria-live="polite"
      >
        正在加载最近任务…
      </div>
      <div
        v-else-if="hasRecentError"
        class="recent-state recent-state--error"
        data-testid="recent-error"
        role="alert"
      >
        <strong>最近任务加载失败</strong>
        <span>请检查网络后重试，已有任务不会受到影响。</span>
        <button
          type="button"
          class="oa-button oa-button--secondary"
          @click="loadRecentTasks()"
        >
          重新加载
        </button>
      </div>
      <div
        v-else-if="!recentTasks.length"
        class="recent-state"
        data-testid="recent-empty"
      >
        <strong>还没有任务</strong>
        <span>创建任务后，服务端进度和输出类型会显示在这里。</span>
      </div>
      <ul v-else class="recent-grid">
        <li
          v-for="task in recentTasks"
          :key="task.task_id"
          data-testid="recent-task"
        >
          <RouterLink
            class="recent-task"
            :to="{
              name: 'workflow-task-detail',
              params: { taskId: task.task_id },
            }"
          >
            <div class="recent-task__heading">
              <div>
                <span class="recent-task__kind">
                  {{ workflowTaskOutputLabel(task.output_kinds) }}
                </span>
                <h3>{{ task.title }}</h3>
              </div>
              <span
                class="status-pill"
                :data-status="task.status"
              >
                {{ workflowTaskStatusLabel(task.status) }}
              </span>
            </div>
            <div class="recent-task__progress">
              <span>当前进度</span>
              <strong class="oa-tabular">{{ task.progress }}%</strong>
            </div>
            <progress
              :value="task.progress"
              max="100"
              :aria-label="`${task.title}进度 ${task.progress}%`"
            >
              {{ task.progress }}%
            </progress>
            <footer>
              <span>
                更新于
                <time :datetime="task.updated_at">
                  {{ formatUpdatedAt(task.updated_at) }}
                </time>
              </span>
              <strong>查看详情</strong>
            </footer>
          </RouterLink>
        </li>
      </ul>
    </section>
  </section>
</template>

<style scoped>
.home-page {
  padding: clamp(52px, 8vw, 96px) clamp(20px, 5vw, 64px) 56px;
}

header {
  margin: 0 auto 40px;
  text-align: center;
}

header p {
  margin: 0 0 10px;
  color: var(--oa-accent);
  font-size: 13px;
  font-weight: 750;
}

h1 {
  margin: 0;
  font-size: clamp(36px, 5vw, 58px);
  line-height: 1.12;
  text-wrap: balance;
}

header span {
  display: block;
  margin-top: 18px;
  color: var(--oa-muted);
  font-size: 19px;
}

.choice-grid {
  display: grid;
  max-width: 1180px;
  margin: 0 auto;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 24px;
}

.workflow-choice {
  position: relative;
  display: grid;
  min-height: 176px;
  border: 1px solid #cbd5e1;
  border-radius: 12px;
  padding: 24px;
  color: var(--oa-ink);
  background: rgb(255 255 255 / 72%);
  text-align: left;
  grid-template-rows: auto auto 1fr;
  gap: 8px;
  transition:
    transform 120ms ease-out,
    border-color 160ms ease-out,
    background-color 160ms ease-out,
    box-shadow 160ms ease-out;
}

.workflow-choice:active {
  transform: scale(0.98);
}

.workflow-choice.selected {
  border-color: #0b6ed0;
  background: #fff;
  box-shadow: 0 12px 28px rgb(15 23 42 / 7%);
}

.workflow-choice__kind {
  width: fit-content;
  border-radius: 6px;
  padding: 5px 7px;
  color: var(--oa-accent);
  background: #eaf3f8;
  font-size: 12px;
  font-weight: 800;
}

.workflow-choice strong {
  margin-top: 8px;
  font-size: 21px;
}

.workflow-choice small {
  color: var(--oa-muted);
  font-size: 15px;
  line-height: 1.6;
}

.selected-mark {
  position: absolute;
  top: 16px;
  right: 16px;
  color: #0b6ed0;
  font-size: 13px;
  font-weight: 700;
}

.continue-button {
  display: block;
  min-width: 210px;
  margin: 40px auto 62px;
}

@media (max-width: 820px) {
  .choice-grid {
    grid-template-columns: 1fr;
  }

  .workflow-choice {
    min-height: 148px;
  }

  header {
    text-align: left;
  }

  .continue-button {
    width: auto;
    margin-left: 0;
  }

  .recent-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 420px) {
  .home-page {
    padding-right: 16px;
    padding-left: 16px;
  }

  .recent-task__heading {
    display: grid;
  }

  .recent-task footer {
    align-items: flex-start;
  }
}
</style>

<style scoped src="./home-recent-tasks.css"></style>
