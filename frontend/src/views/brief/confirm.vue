<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { ApiError } from "@/api/request";
import { briefApi } from "@/modules/briefs/api";
import type {
  BriefRevision,
  PreflightResult,
} from "@/modules/briefs/types";
import { workspaceApi } from "@/modules/workspace/api";
import { useSessionStore } from "@/store/session";

import UnitResolutionList from "./components/unit-resolution-list.vue";


const route = useRoute();
const router = useRouter();
const session = useSessionStore();
const brief = ref<BriefRevision | null>(null);
const preflight = ref<PreflightResult | null>(null);
const goal = ref("");
const audience = ref("");
const isLoading = ref(true);
const isSaving = ref(false);
const isConfirming = ref(false);
const errorMessage = ref("");
const isConfirmed = ref(false);
const unitResolutionValues = ref<Record<string, string>>({});
const generationIdempotencyKey = crypto.randomUUID();

const briefId = computed(() => String(route.params.briefId ?? ""));
const activeBriefId = computed(() => brief.value?.brief_id ?? briefId.value);
const blockingConflicts = computed(
  () =>
    preflight.value?.conflicts.filter((item) =>
      ["blocking", "incompatible"].includes(item.level),
    ) ?? [],
);
const unitConflicts = computed(() =>
  blockingConflicts.value.filter((item) => item.code === "unit_unknown"),
);
const otherBlockingConflicts = computed(() =>
  blockingConflicts.value.filter((item) => item.code !== "unit_unknown"),
);
const confirmationConflicts = computed(
  () =>
    preflight.value?.conflicts.filter(
      (item) => item.level === "needs_confirmation",
    ) ?? [],
);
const canConfirm = computed(
  () =>
    Boolean(preflight.value) &&
    !preflight.value?.has_blockers &&
    !isConfirming.value &&
    !isConfirmed.value,
);

function requireAccessToken() {
  if (!session.accessToken) {
    throw new Error("登录状态已失效，请重新登录");
  }
  return session.accessToken;
}

function readableError(error: unknown) {
  if (error instanceof ApiError || error instanceof Error) {
    return error.message;
  }
  return "无法加载 Brief，请稍后重试";
}

function templateLabel(templateCode: string, version: string) {
  const labels: Record<string, string> = {
    "ppt.executive-blue.v1": "高管钢蓝",
    "ppt.operating-review.v1": "经营复盘",
    "ppt.data-story.v1": "数据叙事",
    "excel.analysis-dashboard.v1": "分析看板",
    "excel.operating-review.v1": "经营复盘",
  };
  return `${labels[templateCode] ?? "系统模板"} · v${version}`;
}

function conflictKey(code: string, evidenceIds: string[]) {
  return `${code}:${evidenceIds.join(",")}`;
}

async function refreshPreflight() {
  preflight.value = await briefApi.preflight(
    activeBriefId.value,
    requireAccessToken(),
  );
  const nextValues: Record<string, string> = {};
  for (const conflict of preflight.value.conflicts) {
    if (conflict.code === "unit_unknown") {
      const key = conflictKey(conflict.code, conflict.evidence_ids);
      nextValues[key] = unitResolutionValues.value[key] ?? "";
    }
  }
  unitResolutionValues.value = nextValues;
}

async function loadBrief() {
  isLoading.value = true;
  errorMessage.value = "";
  try {
    brief.value = await briefApi.getBrief(
      briefId.value,
      requireAccessToken(),
    );
    goal.value = brief.value.content.goal;
    audience.value = brief.value.content.audience;
    await refreshPreflight();
    isConfirmed.value = brief.value.status === "queued";
  } catch (error) {
    errorMessage.value = readableError(error);
  } finally {
    isLoading.value = false;
  }
}

async function saveBrief() {
  if (!brief.value || !goal.value.trim() || !audience.value.trim()) {
    errorMessage.value = "目标和受众不能为空";
    return;
  }
  const unresolvedUnit = unitConflicts.value.find(
    (item) =>
      !unitResolutionValues.value[
        conflictKey(item.code, item.evidence_ids)
      ],
  );
  if (unresolvedUnit) {
    errorMessage.value = "请先为所有引用数值选择明确单位";
    return;
  }
  isSaving.value = true;
  errorMessage.value = "";
  try {
    const resolutions = unitConflicts.value.map((item) => ({
      code: item.code,
      evidence_ids: item.evidence_ids,
      action: "assign_unit" as const,
      value:
        unitResolutionValues.value[
          conflictKey(item.code, item.evidence_ids)
        ],
    }));
    brief.value = await briefApi.reviseBrief(
      brief.value.brief_id,
      {
        expected_revision: brief.value.revision,
        goal: goal.value.trim(),
        audience: audience.value.trim(),
        ...(resolutions.length ? { resolutions } : {}),
      },
      requireAccessToken(),
    );
    await refreshPreflight();
  } catch (error) {
    errorMessage.value = readableError(error);
  } finally {
    isSaving.value = false;
  }
}

async function confirmBrief() {
  if (!preflight.value || preflight.value.has_blockers) {
    return;
  }
  isConfirming.value = true;
  errorMessage.value = "";
  try {
    preflight.value = await briefApi.confirm(
      activeBriefId.value,
      preflight.value.estimated_credits,
      requireAccessToken(),
    );
    const generation = await workspaceApi.createGeneration(
      activeBriefId.value,
      generationIdempotencyKey,
      requireAccessToken(),
    );
    isConfirmed.value = true;
    await router.push({
      name: "generation-detail",
      params: { taskId: generation.task_id },
    });
  } catch (error) {
    errorMessage.value = readableError(error);
  } finally {
    isConfirming.value = false;
  }
}

onMounted(loadBrief);
</script>

<template>
  <section class="brief-page" lang="zh-CN">
    <a class="back-link" href="/">← 返回工作台</a>

    <div v-if="isLoading" class="state-panel" aria-live="polite">
      正在核对 Brief 和生成条件…
    </div>

    <div v-else-if="errorMessage && !brief" class="state-panel state-panel--error">
      <p>{{ errorMessage }}</p>
      <button type="button" class="secondary-button" @click="loadBrief">
        重新加载
      </button>
    </div>

    <template v-else-if="brief && preflight">
      <header class="page-heading">
        <p class="eyebrow">生成前确认 · Revision {{ brief.revision }}</p>
        <h1>确认后进入生成队列</h1>
        <p>检查材料、输出和冲突项。预计积分确认后不会提高。</p>
      </header>

      <div class="workspace">
        <section class="brief-editor" aria-labelledby="brief-editor-title">
          <div class="section-heading">
            <div>
              <p class="section-kicker">Structured Brief</p>
              <h2 id="brief-editor-title">汇报目标</h2>
            </div>
            <span class="revision-badge">R{{ brief.revision }}</span>
          </div>

          <label for="brief-goal">目标</label>
          <textarea
            id="brief-goal"
            v-model="goal"
            data-testid="brief-goal"
            rows="3"
          />

          <label for="brief-audience">受众</label>
          <input id="brief-audience" v-model="audience" type="text" />

          <div class="editor-footer">
            <span>使用材料 {{ brief.content.source_asset_versions.length }} 个</span>
            <button
              type="button"
              class="secondary-button"
              data-testid="save-brief"
              :disabled="isSaving"
              @click="saveBrief"
            >
              {{ isSaving ? "保存中…" : "保存为新 Revision" }}
            </button>
          </div>
        </section>

        <aside class="confirmation-panel" aria-labelledby="output-title">
          <div class="section-heading">
            <div>
              <p class="section-kicker">Output plan</p>
              <h2 id="output-title">本次将生成</h2>
            </div>
          </div>

          <ul class="output-list">
            <li v-for="output in preflight.outputs" :key="output.kind">
              <span class="file-kind">{{ output.kind.toUpperCase() }}</span>
              <span class="output-copy">
                <strong>{{ output.title }}</strong>
                <small :title="output.template_code">
                  {{ templateLabel(output.template_code, output.template_version) }}
                </small>
              </span>
              <span class="output-credit">{{ output.estimated_credits }} 积分</span>
            </li>
          </ul>

          <div
            v-if="blockingConflicts.length"
            class="conflict-panel"
            role="alert"
          >
            <strong>还有 {{ blockingConflicts.length }} 个阻断项</strong>
            <ul>
              <li
                v-for="conflict in otherBlockingConflicts"
                :key="conflictKey(conflict.code, conflict.evidence_ids)"
              >
                {{ conflict.message }}
              </li>
            </ul>
            <UnitResolutionList
              v-if="unitConflicts.length"
              v-model="unitResolutionValues"
              :conflicts="unitConflicts"
            />
          </div>

          <div
            v-if="confirmationConflicts.length"
            class="review-panel"
            aria-live="polite"
          >
            <strong>确认前请复核</strong>
            <ul>
              <li v-for="conflict in confirmationConflicts" :key="conflict.code">
                {{ conflict.message }}
              </li>
            </ul>
          </div>

          <p
            v-if="errorMessage"
            class="inline-error"
            role="alert"
          >
            {{ errorMessage }}
          </p>

          <div class="credit-summary" data-testid="estimated-credits">
            <span>预计积分</span>
            <strong>{{ preflight.estimated_credits }}</strong>
          </div>

          <button
            type="button"
            class="primary-button"
            data-testid="confirm-brief"
            :disabled="!canConfirm"
            @click="confirmBrief"
          >
            {{
              isConfirmed
                ? "任务已创建"
                : isConfirming
                  ? "正在创建任务…"
                  : "确认并开始生成"
            }}
          </button>
          <p class="boundary-note">
            确认后将创建真实任务，并按已接受的估算预留积分。
          </p>
        </aside>
      </div>
    </template>
  </section>
</template>

<style scoped>
.page-heading {
  max-width: 720px;
  margin: 38px auto 30px;
  text-align: center;
}

.eyebrow,
.section-kicker {
  margin: 0 0 8px;
  color: var(--steel);
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.page-heading h1 {
  margin: 0;
  font-size: clamp(32px, 4vw, 46px);
  line-height: 1.12;
  text-wrap: balance;
}

.page-heading > p:last-child {
  margin: 14px 0 0;
  color: var(--muted);
  line-height: 1.7;
}

.workspace {
  display: grid;
  max-width: 1120px;
  margin: 0 auto;
  grid-template-columns: minmax(0, 1.08fr) minmax(340px, 0.92fr);
  gap: 24px;
  align-items: start;
}

.brief-editor,
.confirmation-panel,
.state-panel {
  border-radius: 16px;
  background: var(--surface);
  box-shadow:
    0 1px 3px rgb(21 35 56 / 12%),
    0 16px 38px rgb(21 35 56 / 7%);
}

.brief-editor,
.confirmation-panel {
  padding: 28px;
}

.section-heading,
.editor-footer,
.credit-summary,
.output-list li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.section-heading h2 {
  margin: 0;
  font-size: 24px;
  letter-spacing: -0.012em;
}

.revision-badge,
.file-kind {
  border-radius: 8px;
  background: oklch(0.94 0.025 247);
  color: var(--steel-dark);
  font-variant-numeric: tabular-nums;
  font-weight: 750;
}

.revision-badge {
  padding: 6px 10px;
}

label {
  display: block;
  margin: 24px 0 8px;
  font-weight: 700;
}

textarea,
input {
  width: 100%;
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 12px 14px;
  color: var(--ink);
  background: oklch(1 0 0);
  font: inherit;
  line-height: 1.65;
}

textarea:focus-visible,
input:focus-visible,
button:focus-visible,
a:focus-visible {
  outline: 3px solid oklch(0.72 0.1 247 / 45%);
  outline-offset: 2px;
}

.editor-footer {
  margin-top: 24px;
  color: var(--muted);
}

.output-list {
  margin: 22px 0;
  padding: 0;
  list-style: none;
}

.output-list li {
  padding: 16px 0;
  border-bottom: 1px solid var(--line);
}

.file-kind {
  min-width: 58px;
  padding: 7px 8px;
  text-align: center;
}

.output-copy {
  display: grid;
  flex: 1;
  gap: 4px;
}

.output-copy small {
  color: var(--muted);
  overflow-wrap: anywhere;
}

.output-credit,
.credit-summary strong {
  font-variant-numeric: tabular-nums;
}

</style>
<style scoped src="./confirm-actions.css"></style>
