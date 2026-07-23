<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute } from "vue-router";

import { ApiError } from "@/api/request";
import { workspaceApi } from "@/modules/workspace/api";
import type {
  GenerationOutput,
  GenerationTask,
} from "@/modules/workspace/types";
import { useSessionStore } from "@/store/session";

const route = useRoute();
const session = useSessionStore();
const task = ref<GenerationTask | null>(null);
const outputs = ref<GenerationOutput[]>([]);
const isLoading = ref(true);
const errorMessage = ref("");
const downloadingKind = ref<string | null>(null);

const taskId = computed(() => String(route.params.taskId ?? ""));
const statusCopy = computed(() => {
  const status = task.value?.status;
  if (status === "succeeded") {
    return { title: "任务已完成", detail: "全部文件已通过检查，可以下载。" };
  }
  if (status === "partial_success") {
    return { title: "部分完成", detail: "可下载已通过检查的文件，失败输出不会扣费。" };
  }
  if (status === "provider_uncertain") {
    return {
      title: "Provider 状态暂不确定",
      detail: "系统不会自动重试或重复扣费，需要等待受审计的处理结果。",
    };
  }
  if (status === "failed") {
    return { title: "任务未完成", detail: "请根据稳定错误信息调整材料后重试。" };
  }
  return { title: "任务生成中", detail: "进度来自持久任务状态，刷新页面不会丢失。" };
});

function requireToken() {
  if (!session.accessToken) throw new Error("登录状态已失效，请重新登录");
  return session.accessToken;
}

function readableError(error: unknown) {
  if (error instanceof ApiError || error instanceof Error) return error.message;
  return "无法加载任务，请稍后重试";
}

async function load() {
  isLoading.value = true;
  errorMessage.value = "";
  try {
    const accessToken = requireToken();
    task.value = await workspaceApi.getGeneration(taskId.value, accessToken);
    const response = await workspaceApi.getGenerationOutputs(
      taskId.value,
      accessToken,
    );
    outputs.value = response.outputs;
  } catch (error) {
    errorMessage.value = readableError(error);
  } finally {
    isLoading.value = false;
  }
}

async function download(output: GenerationOutput) {
  if (!output.asset_id || !output.download_allowed) return;
  downloadingKind.value = output.output_kind;
  errorMessage.value = "";
  try {
    const blob = await workspaceApi.downloadAsset(
      output.asset_id,
      requireToken(),
    );
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `office-ai-${taskId.value}.${output.output_kind}`;
    anchor.click();
    URL.revokeObjectURL(url);
  } catch (error) {
    errorMessage.value = readableError(error);
  } finally {
    downloadingKind.value = null;
  }
}

onMounted(load);
</script>

<template>
  <section class="result-page" lang="zh-CN">
    <nav class="breadcrumb" aria-label="面包屑">
      <RouterLink to="/tasks">任务</RouterLink>
      <span>/</span>
      <span>{{ taskId }}</span>
    </nav>

    <div v-if="isLoading" class="state-panel" aria-live="polite">正在加载任务与质量结果…</div>
    <div v-else-if="errorMessage && !task" class="state-panel state-panel--error">
      <p>{{ errorMessage }}</p>
      <button class="oa-button oa-button--secondary" type="button" @click="load">重新加载</button>
    </div>

    <template v-else-if="task">
      <header class="result-heading">
        <span class="result-mark" :class="`result-mark--${task.status}`" aria-hidden="true">
          {{ task.status === "succeeded" ? "✓" : task.status === "partial_success" ? "!" : "·" }}
        </span>
        <h1>{{ statusCopy.title }}</h1>
        <p>{{ statusCopy.detail }}</p>
        <div class="progress-track" :aria-label="`生成进度 ${task.progress}%`">
          <span :style="{ width: `${task.progress}%` }" />
        </div>
        <strong class="oa-tabular">{{ task.progress }}%</strong>
      </header>

      <section class="output-section" aria-labelledby="outputs-title">
        <div class="section-title">
          <h2 id="outputs-title">生成文件</h2>
          <button class="oa-button oa-button--secondary" type="button" @click="load">刷新状态</button>
        </div>
        <div v-if="outputs.length" class="output-list">
          <article v-for="output in outputs" :key="output.output_kind">
            <span class="file-kind">{{ output.output_kind.toUpperCase() }}</span>
            <div>
              <h3>{{ output.output_kind === "pptx" ? "销售经营汇报" : "销售数据分析与经营看板" }}</h3>
              <p v-if="output.download_allowed" class="success-copy">已通过质量检查，可以下载</p>
              <p v-else class="blocked-copy">
                {{ output.output_kind.toUpperCase() }} 未通过质量检查
                <span v-if="output.error_category">· {{ output.error_category }}</span>
              </p>
            </div>
            <button
              v-if="output.download_allowed"
              class="oa-button oa-button--secondary"
              data-testid="download-output"
              type="button"
              :disabled="downloadingKind === output.output_kind"
              @click="download(output)"
            >
              {{ downloadingKind === output.output_kind ? "准备中…" : `下载 ${output.output_kind.toUpperCase()}` }}
            </button>
            <span v-else class="download-disabled">不可下载</span>
          </article>
        </div>
        <div v-else class="empty-output">
          当前还没有可下载输出。Provider 状态不确定时不会暴露下载入口。
        </div>
      </section>

      <p v-if="errorMessage" class="oa-error" role="alert">{{ errorMessage }}</p>

      <section class="detail-rows">
        <details>
          <summary>质量检查 <span>{{ outputs.every((item) => item.download_allowed) ? "全部通过" : "查看结果" }}</span></summary>
          <p>每个输出独立执行质量 gate；只有 validated artifact 完整性通过时才能下载。</p>
        </details>
        <details>
          <summary>积分明细 <span class="oa-tabular">已结算 {{ task.settled_credits }}</span></summary>
          <p>预计 {{ task.estimated_credits }} 积分，只结算成功输出，失败额度会释放。</p>
        </details>
      </section>

      <footer>
        <span class="oa-tabular">任务编号 {{ task.task_id }}</span>
        <RouterLink to="/">基于本次内容再生成</RouterLink>
        <RouterLink to="/tasks">返回任务列表</RouterLink>
      </footer>
    </template>
  </section>
</template>

<style scoped>
.result-page {
  width: min(100%, 1120px);
  margin: 0 auto;
  padding: 30px clamp(18px, 4vw, 44px) 56px;
}

.breadcrumb {
  display: flex;
  min-height: 40px;
  align-items: center;
  gap: 10px;
  color: var(--oa-muted);
}

.breadcrumb a {
  color: var(--oa-muted);
  text-decoration: none;
}

.result-heading {
  max-width: 720px;
  margin: 32px auto 48px;
  text-align: center;
}

.result-mark {
  display: grid;
  width: 70px;
  height: 70px;
  margin: 0 auto 18px;
  place-items: center;
  border: 2px solid var(--oa-accent);
  border-radius: 50%;
  color: var(--oa-accent);
  font-size: 28px;
  font-weight: 750;
}

.result-mark--succeeded {
  border-color: var(--oa-success);
  color: var(--oa-success);
}

.result-mark--partial_success,
.result-mark--provider_uncertain {
  border-color: var(--oa-warning);
  color: var(--oa-warning);
}

h1 {
  margin: 0;
  font-size: clamp(32px, 5vw, 46px);
  line-height: 1.18;
}

.result-heading p {
  margin: 14px 0 22px;
  color: var(--oa-muted);
  line-height: 1.7;
}

.progress-track {
  height: 6px;
  overflow: hidden;
  border-radius: 999px;
  background: #e2e8f0;
}

.progress-track span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: var(--oa-accent);
}

.result-heading > strong {
  display: block;
  margin-top: 8px;
  color: var(--oa-muted);
}

.output-section {
  margin-bottom: 14px;
}

.section-title,
.output-list article,
footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
}

h2,
h3 {
  margin: 0;
}

.output-list {
  overflow: hidden;
  margin-top: 14px;
  border: 1px solid var(--oa-line);
  border-radius: 12px;
  background: #fff;
}

.output-list article {
  min-height: 108px;
  padding: 18px 22px;
}

.output-list article + article {
  border-top: 1px solid var(--oa-line);
}

.file-kind {
  display: grid;
  width: 56px;
  height: 56px;
  flex: 0 0 auto;
  place-items: center;
  border-radius: 10px;
  color: var(--oa-accent);
  background: #eaf3f8;
  font-size: 12px;
  font-weight: 800;
}

.output-list article > div {
  flex: 1;
}

.output-list p {
  margin: 6px 0 0;
  font-size: 14px;
}

.success-copy {
  color: var(--oa-success);
}

.blocked-copy {
  color: var(--oa-danger);
}

.download-disabled {
  color: var(--oa-muted);
}

.empty-output,
.state-panel {
  border: 1px solid var(--oa-line);
  border-radius: 12px;
  padding: 24px;
  color: var(--oa-muted);
  background: #fff;
  line-height: 1.7;
}

.state-panel {
  margin-top: 48px;
}

.state-panel--error {
  color: var(--oa-danger);
}

.detail-rows {
  display: grid;
  gap: 10px;
}

details {
  border: 1px solid var(--oa-line);
  border-radius: 8px;
  padding: 0 18px;
  background: #fff;
}

summary {
  display: flex;
  min-height: 54px;
  align-items: center;
  justify-content: space-between;
  cursor: pointer;
}

details p {
  margin: 0 0 18px;
  color: var(--oa-muted);
  line-height: 1.7;
}

footer {
  margin-top: 30px;
  padding-top: 24px;
  border-top: 1px solid var(--oa-line);
  color: var(--oa-muted);
  font-size: 14px;
}

@media (max-width: 680px) {
  .result-heading {
    text-align: left;
  }

  .result-mark {
    margin-left: 0;
  }

  .output-list article {
    align-items: flex-start;
    flex-wrap: wrap;
  }

  .output-list article > div {
    min-width: calc(100% - 80px);
  }

  footer {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
