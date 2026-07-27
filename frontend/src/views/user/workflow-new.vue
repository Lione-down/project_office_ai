<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { ApiError } from "@/api/request";
import { workspaceApi } from "@/modules/workspace/api";
import type {
  AssetSummary,
  BriefGenerationSelection,
  WorkspaceOptions,
} from "@/modules/workspace/types";
import { useSessionStore } from "@/store/session";

const PROCESSING_POLL_INTERVAL_MS = 1500;

const route = useRoute();
const router = useRouter();
const session = useSessionStore();
const options = ref<WorkspaceOptions | null>(null);
const projectId = ref("");
const selectedAssetIds = ref<string[]>([]);
const selectedSkillCodes = ref<string[]>([]);
const selectedTermLibraryKeys = ref<string[]>([]);
const modelId = ref("");
const goal = ref("形成可供销售管理层决策的经营复盘");
const audience = ref("销售管理层");
const isLoading = ref(true);
const isSubmitting = ref(false);
const isUploading = ref(false);
const errorMessage = ref("");
let processingPollTimer: ReturnType<typeof setTimeout> | undefined;

const mode = computed(() => String(route.query.mode ?? "combined"));
const projectAssets = computed(
  () =>
    options.value?.assets.filter(
      (asset) => asset.project_id === projectId.value,
    ) ?? [],
);
const readyAssets = computed(() => projectAssets.value.filter(isAssetReady));
const hasPendingAssets = computed(
  () => projectAssets.value.some((asset) =>
    !["ready", "rejected", "deleted"].includes(asset.processing_status),
  ),
);
const hasRejectedAssets = computed(() =>
  projectAssets.value.some(
    (asset) =>
      asset.processing_status === "rejected" ||
      asset.manifest_status === "invalid",
  ),
);
const canSubmit = computed(
  () =>
    !isLoading.value &&
    !isSubmitting.value &&
    selectedAssetIds.value.length > 0 &&
    selectedAssetIds.value.every((assetId) =>
      readyAssets.value.some((asset) => asset.asset_id === assetId),
    ) &&
    selectedSkillCodes.value.length > 0 &&
    Boolean(projectId.value && modelId.value && goal.value.trim() && audience.value.trim()),
);

function isAssetReady(asset: AssetSummary) {
  return (
    asset.processing_status === "ready" &&
    asset.manifest_status === "valid"
  );
}

function assetStatusMessage(asset: AssetSummary) {
  if (isAssetReady(asset)) {
    return `${(asset.byte_size / 1024).toFixed(1)} KB · 可用于生成`;
  }
  if (asset.processing_error_code === "excel_sheet_limit_exceeded") {
    return "未通过：Excel 工作表数量超过 30 个，请精简后重新上传。";
  }
  if (asset.processing_status === "rejected" || asset.manifest_status === "invalid") {
    return `未通过：${asset.processing_error_message || "文件未通过安全处理，请修正后重新上传。"}`;
  }
  if (asset.processing_error_message) {
    return `暂时无法完成处理：${asset.processing_error_message}`;
  }
  return "安全处理中，完成后会自动刷新。";
}

function requireToken() {
  if (!session.accessToken) throw new Error("登录状态已失效，请重新登录");
  return session.accessToken;
}

function readableError(error: unknown) {
  if (error instanceof ApiError || error instanceof Error) return error.message;
  return "无法加载工作流，请稍后重试";
}

function termLibraryKey(libraryId: string, version: number) {
  return `${libraryId}:${version}`;
}

function applyDefaults(loaded: WorkspaceOptions) {
  const project = loaded.projects.find((item) => item.is_default) ?? loaded.projects[0];
  projectId.value = project?.project_id ?? "";
  const wantedKinds =
    mode.value === "combined" ? ["pptx", "xlsx"] : [mode.value];
  selectedSkillCodes.value = loaded.skills
    .filter((skill) => wantedKinds.includes(skill.output_kind))
    .map((skill) => skill.skill_code);
  const model =
    loaded.models.find(
      (item) =>
        item.is_recommended &&
        selectedSkillCodes.value.every((code) => item.allowed_skills.includes(code)),
    ) ?? loaded.models[0];
  modelId.value = model?.model_id ?? "";
  selectedAssetIds.value = loaded.assets
    .filter(
      (asset) =>
        asset.project_id === projectId.value &&
        isAssetReady(asset),
    )
    .slice(0, 1)
    .map((asset) => asset.asset_id);
}

function clearProcessingPoll() {
  if (processingPollTimer !== undefined) {
    clearTimeout(processingPollTimer);
    processingPollTimer = undefined;
  }
}

function scheduleProcessingRefresh() {
  clearProcessingPoll();
  if (!hasPendingAssets.value) return;
  processingPollTimer = setTimeout(() => {
    processingPollTimer = undefined;
    void loadOptions();
  }, PROCESSING_POLL_INTERVAL_MS);
}

async function loadOptions() {
  isLoading.value = options.value === null;
  errorMessage.value = "";
  try {
    const loaded = await workspaceApi.loadOptions(requireToken());
    options.value = loaded;
    applyDefaults(loaded);
  } catch (error) {
    errorMessage.value = readableError(error);
  } finally {
    isLoading.value = false;
    scheduleProcessingRefresh();
  }
}

async function upload(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  isUploading.value = true;
  errorMessage.value = "";
  try {
    await workspaceApi.uploadAsset(
      file,
      projectId.value || undefined,
      crypto.randomUUID(),
      requireToken(),
    );
    await loadOptions();
  } catch (error) {
    errorMessage.value = readableError(error);
  } finally {
    input.value = "";
    isUploading.value = false;
  }
}

async function submit() {
  if (!canSubmit.value) return;
  const selection: BriefGenerationSelection = {
    project_id: projectId.value,
    asset_ids: selectedAssetIds.value,
    term_library_versions:
      options.value?.termLibraries
        .filter((library) =>
          selectedTermLibraryKeys.value.includes(
            termLibraryKey(library.library_id, library.version),
          ),
        )
        .map((library) => ({
          library_id: library.library_id,
          version: library.version,
        })) ?? [],
    skill_codes: selectedSkillCodes.value,
    model_id: modelId.value,
    goal: goal.value.trim(),
    audience: audience.value.trim(),
    must_include: [],
    must_exclude: [],
  };
  isSubmitting.value = true;
  errorMessage.value = "";
  try {
    const brief = await workspaceApi.generateBrief(selection, requireToken());
    await router.push({
      name: "brief-confirm",
      params: { briefId: brief.brief_id },
    });
  } catch (error) {
    errorMessage.value = readableError(error);
  } finally {
    isSubmitting.value = false;
  }
}

onMounted(loadOptions);
onBeforeUnmount(clearProcessingPoll);
</script>

<template>
  <section class="workflow-page" lang="zh-CN">
    <RouterLink class="back-link" to="/">← 返回工作台</RouterLink>

    <header class="workflow-heading">
      <p>新建生成任务</p>
      <h1>准备材料与生成目标</h1>
      <span>确认材料、输出类型和模型后，系统会先生成可复核的 Brief。</span>
    </header>

    <div v-if="isLoading" class="state-panel" aria-live="polite">
      正在加载项目、材料和模型…
    </div>
    <div v-else-if="errorMessage && !options" class="state-panel state-panel--error">
      <p>{{ errorMessage }}</p>
      <button class="oa-button oa-button--secondary" type="button" @click="loadOptions">
        重新加载
      </button>
    </div>

    <form v-else-if="options" class="workflow-form" data-testid="workflow-submit" @submit.prevent="submit">
      <section class="workflow-section">
        <div class="section-heading">
          <span>1</span>
          <div>
            <h2>项目与材料</h2>
            <p>只使用完成安全处理并生成 Evidence Manifest 的材料。</p>
          </div>
        </div>
        <label class="oa-field">
          <span>项目</span>
          <select v-model="projectId" class="oa-input">
            <option v-if="!options.projects.length" disabled value="">
              上传首份材料后自动创建默认项目
            </option>
            <option v-for="project in options.projects" :key="project.project_id" :value="project.project_id">
              {{ project.name }}
            </option>
          </select>
        </label>
        <div class="asset-list">
          <div
            v-for="asset in projectAssets"
            :key="asset.asset_id"
            class="asset-list__item"
            :class="{ 'asset-list__item--disabled': !isAssetReady(asset) }"
          >
            <input
              v-if="isAssetReady(asset)"
              v-model="selectedAssetIds"
              type="checkbox"
              :value="asset.asset_id"
            />
            <span v-else class="asset-list__status-marker" aria-hidden="true">!</span>
            <span>
              <strong>{{ asset.original_filename }}</strong>
              <small>{{ assetStatusMessage(asset) }}</small>
            </span>
          </div>
        </div>
        <p v-if="!readyAssets.length" class="status-note" role="status">
          材料完成安全处理后才能继续。
          <span v-if="hasPendingAssets">材料正在安全处理中，完成后会自动刷新。</span>
          <span v-else-if="hasRejectedAssets">
            当前材料未通过安全处理，请按上方原因修正后重新上传。
          </span>
        </p>
        <label class="upload-button">
          <input
            data-testid="workflow-file-input"
            type="file"
            :disabled="isUploading"
            @change="upload"
          />
          {{ isUploading ? "上传中…" : "上传一份材料" }}
        </label>
      </section>

      <section class="workflow-section">
        <div class="section-heading">
          <span>2</span>
          <div>
            <h2>说明目标</h2>
            <p>目标和受众会进入不可变 Brief revision。</p>
          </div>
        </div>
        <label class="oa-field">
          <span>生成目标</span>
          <textarea v-model="goal" class="oa-input" rows="3" />
        </label>
        <label class="oa-field">
          <span>阅读受众</span>
          <input v-model="audience" class="oa-input" />
        </label>
      </section>

      <section class="workflow-section">
        <div class="section-heading">
          <span>3</span>
          <div>
            <h2>Skill、模型与模板</h2>
            <p>Alpha 只使用已发布 Skill、可见模型和系统认证模板。</p>
          </div>
        </div>
        <div class="skill-grid">
          <label
            v-for="skill in options.skills"
            :key="skill.skill_code"
            :class="{ selected: selectedSkillCodes.includes(skill.skill_code) }"
          >
            <input v-model="selectedSkillCodes" type="checkbox" :value="skill.skill_code" />
            <strong>{{ skill.display_name }}</strong>
            <small>{{ skill.output_kind.toUpperCase() }} · v{{ skill.version }}</small>
          </label>
        </div>
        <label class="oa-field">
          <span>模型</span>
          <select v-model="modelId" class="oa-input">
            <option v-for="model in options.models" :key="model.model_id" :value="model.model_id">
              {{ model.display_name }}{{ model.is_recommended ? " · 推荐" : "" }}
            </option>
          </select>
        </label>
        <fieldset v-if="options.termLibraries.length" class="term-library-list">
          <legend>术语库版本</legend>
          <label v-for="library in options.termLibraries" :key="termLibraryKey(library.library_id, library.version)">
            <input
              v-model="selectedTermLibraryKeys"
              data-testid="term-library-version"
              type="checkbox"
              :value="termLibraryKey(library.library_id, library.version)"
            />
            <span>{{ library.name }} · v{{ library.version }}</span>
          </label>
        </fieldset>
        <p class="template-note">模板将在 Preflight 中按输出类型锁定并显示版本。</p>
      </section>

      <p v-if="errorMessage" class="oa-error" role="alert">{{ errorMessage }}</p>
      <button
        class="oa-button oa-button--primary primary-action"
        data-testid="workflow-primary-action"
        type="submit"
        :disabled="!canSubmit"
      >
        {{ isSubmitting ? "正在整理 Brief…" : "继续到生成前确认" }}
      </button>
    </form>
  </section>
</template>

<style scoped>
.workflow-page {
  width: min(100%, 1040px);
  margin: 0 auto;
  padding: 32px clamp(18px, 4vw, 48px) 64px;
}

.back-link {
  display: inline-flex;
  min-height: 40px;
  align-items: center;
  color: var(--oa-ink);
  text-decoration: none;
}

.workflow-heading {
  margin: 28px 0 34px;
}

.workflow-heading p {
  margin: 0 0 8px;
  color: var(--oa-accent);
  font-size: 13px;
  font-weight: 750;
}

h1 {
  margin: 0;
  font-size: clamp(32px, 5vw, 46px);
  line-height: 1.15;
  text-wrap: balance;
}

.workflow-heading span,
.section-heading p,
.template-note {
  color: var(--oa-muted);
  line-height: 1.7;
}

.workflow-heading > span {
  display: block;
  margin-top: 12px;
}

.workflow-form {
  display: grid;
  gap: 20px;
}

.workflow-section,
.state-panel {
  border: 1px solid var(--oa-line);
  border-radius: 14px;
  padding: clamp(22px, 4vw, 32px);
  background: #fff;
  box-shadow: 0 10px 28px rgb(15 23 42 / 5%);
}

.section-heading {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  margin-bottom: 24px;
}

.section-heading > span {
  display: grid;
  width: 32px;
  height: 32px;
  flex: 0 0 auto;
  place-items: center;
  border-radius: 50%;
  color: #fff;
  background: var(--oa-accent);
  font-weight: 750;
}

h2,
.section-heading p {
  margin: 0;
}

h2 {
  font-size: 22px;
}

.asset-list,
.skill-grid {
  display: grid;
  margin: 18px 0;
  gap: 10px;
}

.asset-list__item,
.skill-grid label {
  display: flex;
  min-height: 64px;
  align-items: center;
  gap: 12px;
  border: 1px solid var(--oa-line);
  border-radius: 10px;
  padding: 12px 14px;
  background: #fff;
}

.asset-list__item--disabled {
  border-color: #fed7aa;
  background: #fffaf3;
}

.asset-list__status-marker {
  display: grid;
  width: 20px;
  height: 20px;
  flex: 0 0 auto;
  place-items: center;
  border-radius: 50%;
  color: #fff;
  background: var(--oa-warning);
  font-size: 12px;
  font-weight: 750;
}

.skill-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.skill-grid label {
  display: grid;
  grid-template-columns: auto 1fr;
}

.skill-grid label.selected {
  border-color: #0b6ed0;
  background: #f5f9fd;
}

.asset-list input,
.skill-grid input {
  width: 18px;
  height: 18px;
  accent-color: var(--oa-accent);
}

.asset-list__item > span:last-child,
.skill-grid strong,
.skill-grid small {
  display: block;
}

.asset-list small,
.skill-grid small {
  display: block;
  margin-top: 4px;
  color: var(--oa-muted);
}

.skill-grid small {
  grid-column: 2;
}

.status-note {
  border-radius: 8px;
  padding: 12px 14px;
  color: var(--oa-warning);
  background: #fff8ed;
  line-height: 1.6;
}

.upload-button {
  display: inline-flex;
  min-height: 42px;
  align-items: center;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  padding: 0 14px;
  font-weight: 650;
  cursor: pointer;
}

.upload-button input {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
}

</style>
<style scoped src="./workflow-new-supplement.css"></style>
