<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";

import { ApiError } from "@/api/request";
import { workspaceApi } from "@/modules/workspace/api";
import type {
  AssetSummary,
  CreditLedger,
  TermLibrarySummary,
  WorkflowTask,
} from "@/modules/workspace/types";
import { useSessionStore } from "@/store/session";

type UserSection = "tasks" | "files" | "templates" | "term-libraries" | "credits";

const props = defineProps<{ section: UserSection }>();
const session = useSessionStore();
const assets = ref<AssetSummary[]>([]);
const tasks = ref<WorkflowTask[]>([]);
const termLibraries = ref<TermLibrarySummary[]>([]);
const creditBalance = ref(0);
const ledger = ref<CreditLedger["entries"]>([]);
const isLoading = ref(false);
const errorMessage = ref("");
let taskPollTimer: ReturnType<typeof setTimeout> | undefined;

const TERMINAL_TASK_STATUSES = new Set([
  "succeeded",
  "partial_success",
  "failed",
  "provider_uncertain",
  "cancelled",
]);

const templates = [
  {
    code: "ppt.executive-blue.v1",
    kind: "PPTX",
    name: "高管钢蓝",
    description: "克制、专业的管理层经营汇报",
  },
  {
    code: "ppt.operating-review.v1",
    kind: "PPTX",
    name: "经营复盘",
    description: "围绕目标、差距和行动项组织内容",
  },
  {
    code: "ppt.data-story.v1",
    kind: "PPTX",
    name: "数据叙事",
    description: "将关键指标转为清晰的数据故事",
  },
  {
    code: "excel.analysis-dashboard.v1",
    kind: "XLSX",
    name: "分析看板",
    description: "面向业务分析的指标与图表看板",
  },
  {
    code: "excel.operating-review.v1",
    kind: "XLSX",
    name: "经营复盘",
    description: "保留明细、汇总和复盘结论",
  },
] as const;

const sectionCopy = computed(() => {
  const copy = {
    tasks: ["我的任务", "查看生成进度、质量状态与输出下载"],
    files: ["我的文件", "管理已上传并经过隔离处理的工作材料"],
    templates: ["系统模板", "使用经过认证的 PPTX 与 XLSX 模板"],
    "term-libraries": ["术语库", "选择已发布版本，保持业务表达一致"],
    credits: ["积分与流水", "查看可用余额和只追加的积分变动记录"],
  } satisfies Record<UserSection, [string, string]>;
  return copy[props.section];
});

function requireToken() {
  if (!session.accessToken) throw new Error("Session 已失效，请重新登录");
  return session.accessToken;
}

function statusLabel(status: string) {
  const labels: Record<string, string> = {
    ready: "可用于生成",
    processing: "处理中",
    quarantined: "隔离检查中",
    failed: "处理失败",
    active: "已发布",
    queued: "排队中",
    running: "进行中",
    awaiting_confirmation: "等待确认",
    succeeded: "已完成",
    partial_success: "部分完成",
    provider_uncertain: "结果待确认",
    cancelled: "已取消",
  };
  return labels[status] ?? status;
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
    props.section !== "tasks" ||
    !tasks.value.some((task) => !TERMINAL_TASK_STATUSES.has(task.status))
  ) {
    return;
  }
  taskPollTimer = setTimeout(() => {
    taskPollTimer = undefined;
    void load();
  }, 3000);
}

function ledgerLabel(type: string) {
  const labels: Record<string, string> = {
    generation_reserve: "生成预留",
    generation_finalize: "生成结算",
    generation_release: "生成释放",
    registration_grant: "注册赠送",
    admin_adjustment: "管理员调整",
  };
  return labels[type] ?? type;
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("zh-CN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

async function load() {
  clearTaskPoll();
  errorMessage.value = "";
  assets.value = [];
  tasks.value = [];
  termLibraries.value = [];
  ledger.value = [];
  if (props.section === "templates") return;
  isLoading.value = true;
  try {
    const token = requireToken();
    if (props.section === "tasks") {
      tasks.value = await workspaceApi.listWorkflowTasks(token);
    } else if (props.section === "credits") {
      const [balanceResult, ledgerResult] = await Promise.all([
        workspaceApi.getCreditBalance(token),
        workspaceApi.getCreditLedger(token),
      ]);
      creditBalance.value = balanceResult.balance;
      ledger.value = ledgerResult.entries;
    } else {
      const options = await workspaceApi.loadOptions(token);
      assets.value = options.assets;
      termLibraries.value = options.termLibraries;
    }
  } catch (error) {
    errorMessage.value =
      error instanceof ApiError || error instanceof Error
        ? error.message
        : "无法加载当前数据";
  } finally {
    isLoading.value = false;
    scheduleTaskPoll();
  }
}

watch(() => props.section, load);
onMounted(load);
onBeforeUnmount(clearTaskPoll);
</script>

<template>
  <section class="resource-page" lang="zh-CN">
    <header>
      <p>个人工作区</p>
      <h1>{{ sectionCopy[0] }}</h1>
      <span>{{ sectionCopy[1] }}</span>
    </header>

    <div v-if="isLoading" class="state-panel" aria-live="polite">正在加载…</div>
    <div v-else-if="errorMessage" class="state-panel state-panel--error">
      <p>{{ errorMessage }}</p>
      <button class="oa-button oa-button--secondary" type="button" @click="load">
        重新加载
      </button>
    </div>

    <template v-else>
      <div v-if="section === 'tasks'" class="table-panel">
        <table>
          <thead>
            <tr>
              <th>任务</th>
              <th>输出</th>
              <th>状态</th>
              <th>进度</th>
              <th>备注 / 失败原因</th>
              <th>积分</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="task in tasks" :key="task.task_id">
              <td>
                <RouterLink
                  class="task-link"
                  :to="{
                    name: 'workflow-task-detail',
                    params: { taskId: task.task_id },
                  }"
                >
                  {{ task.title }}
                </RouterLink>
              </td>
              <td>{{ task.output_kinds.map((kind) => kind.toUpperCase()).join(" + ") }}</td>
              <td><span class="status-pill">{{ statusLabel(task.status) }}</span></td>
              <td class="oa-tabular">{{ task.progress }}%</td>
              <td class="task-note">
                <span>{{ task.note ?? "—" }}</span>
                <strong v-if="task.failure_reason" :title="task.failure_code ?? undefined">
                  {{ task.failure_reason }}
                </strong>
              </td>
              <td class="oa-tabular">
                {{ task.estimated_credits ? task.estimated_credits.toLocaleString("zh-CN") : "—" }}
              </td>
            </tr>
          </tbody>
        </table>
        <div v-if="!tasks.length" class="empty-copy">
          <strong>当前还没有任务</strong>
          <span>创建任务后，Brief、生成进度和失败原因都会保留在这里。</span>
          <RouterLink class="oa-button oa-button--primary" to="/workflow/new">
            新建任务
          </RouterLink>
        </div>
      </div>

      <div v-if="section === 'files'" class="table-panel">
        <table>
          <thead>
            <tr>
              <th>文件名</th>
              <th>类型</th>
              <th>大小</th>
              <th>处理状态</th>
              <th>Evidence</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="asset in assets" :key="asset.asset_id">
              <td>{{ asset.original_filename }}</td>
              <td>{{ asset.file_category.toUpperCase() }}</td>
              <td>{{ Math.ceil(asset.byte_size / 1024).toLocaleString("zh-CN") }} KB</td>
              <td><span class="status-pill">{{ statusLabel(asset.processing_status) }}</span></td>
              <td>{{ asset.manifest_status ? statusLabel(asset.manifest_status) : "尚未生成" }}</td>
            </tr>
          </tbody>
        </table>
        <p v-if="!assets.length" class="empty-copy">尚未上传文件。</p>
      </div>

      <div v-if="section === 'templates'" class="template-grid">
        <article
          v-for="template in templates"
          :key="template.code"
          class="template-card"
          data-testid="system-template"
        >
          <span>{{ template.kind }}</span>
          <h2>{{ template.name }}</h2>
          <p>{{ template.description }}</p>
          <code>{{ template.code }}</code>
        </article>
      </div>

      <div v-if="section === 'term-libraries'" class="table-panel">
        <table>
          <thead>
            <tr>
              <th>术语库</th>
              <th>版本</th>
              <th>状态</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="library in termLibraries" :key="library.library_id">
              <td>{{ library.name }}</td>
              <td>v{{ library.version }}</td>
              <td><span class="status-pill">{{ statusLabel(library.status) }}</span></td>
            </tr>
          </tbody>
        </table>
        <p v-if="!termLibraries.length" class="empty-copy">当前没有已发布术语库。</p>
      </div>

      <template v-if="section === 'credits'">
        <article class="balance-card">
          <span>可用积分</span>
          <strong>{{ creditBalance.toLocaleString("zh-CN") }}</strong>
          <small>积分流水只追加，不覆盖历史记录</small>
        </article>
        <div class="table-panel">
          <table>
            <thead>
              <tr>
                <th>时间</th>
                <th>类型</th>
                <th>关联任务</th>
                <th>变动</th>
                <th>变动后</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="entry in ledger" :key="entry.entry_id">
                <td>{{ formatDate(entry.created_at) }}</td>
                <td>{{ ledgerLabel(entry.entry_type) }}</td>
                <td>{{ entry.task_id ?? "—" }}</td>
                <td :class="{ positive: entry.amount > 0 }">
                  {{ entry.amount > 0 ? "+" : "" }}{{ entry.amount.toLocaleString("zh-CN") }}
                </td>
                <td>{{ entry.balance_after.toLocaleString("zh-CN") }}</td>
              </tr>
            </tbody>
          </table>
          <p v-if="!ledger.length" class="empty-copy">当前没有积分变动。</p>
        </div>
      </template>
    </template>
  </section>
</template>

<style scoped>
.resource-page {
  display: grid;
  gap: 24px;
  padding: clamp(32px, 5vw, 64px);
}
header p {
  margin: 0 0 6px;
  color: var(--oa-accent);
  font-size: 13px;
  font-weight: 750;
}
h1 {
  margin: 0;
  font-size: clamp(30px, 4vw, 44px);
}
header span,
.empty-copy,
.balance-card small {
  color: var(--oa-muted);
}
header span {
  display: block;
  margin-top: 9px;
}
.table-panel,
.balance-card,
.template-card,
.state-panel {
  border: 1px solid var(--oa-line);
  border-radius: 12px;
  background: #fff;
}
.table-panel {
  overflow-x: auto;
}
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
  white-space: nowrap;
}
th,
td {
  min-width: 140px;
  padding: 16px 18px;
  border-bottom: 1px solid var(--oa-line);
  text-align: left;
}
th {
  color: #475569;
  background: #fbfcfc;
  font-size: 13px;
  font-weight: 750;
}
.empty-copy,
.state-panel {
  margin: 0;
  padding: 38px 20px;
  text-align: center;
}
div.empty-copy {
  display: grid;
  justify-items: center;
  gap: 10px;
}

.empty-copy .oa-button {
  margin-top: 10px;
}

.state-panel--error {
  color: var(--oa-danger);
}

.template-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 18px;
}

.template-card {
  min-height: 190px;
  padding: 22px;
}

.template-card > span,
.status-pill {
  width: fit-content;
  border-radius: 5px;
  padding: 4px 7px;
  color: #075985;
  background: #eaf3f8;
  font-size: 12px;
  font-weight: 750;
}

.template-card h2 {
  margin: 20px 0 8px;
  font-size: 20px;
}

.template-card p {
  min-height: 48px;
  margin: 0 0 18px;
  color: var(--oa-muted);
  line-height: 1.6;
}

.template-card code {
  color: #64748b;
  font-size: 12px;
}

.balance-card {
  display: grid;
  width: min(100%, 420px);
  padding: 24px;
  gap: 6px;
}

.balance-card strong {
  font-size: 38px;
  font-variant-numeric: tabular-nums;
}

.positive {
  color: var(--oa-success);
}

.task-link {
  color: var(--oa-ink);
  font-weight: 700;
  text-decoration: none;
}

.task-link:hover {
  color: var(--oa-accent);
}

.task-note {
  display: grid;
  max-width: 320px;
  gap: 4px;
  white-space: normal;
}

.task-note strong {
  color: var(--oa-danger);
  font-weight: 650;
}

@media (max-width: 820px) {
  .template-grid {
    grid-template-columns: 1fr;
  }
}
</style>
