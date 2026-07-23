<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { ApiError } from "@/api/request";
import { workspaceApi } from "@/modules/workspace/api";
import type {
  BriefGenerationSelection,
  WorkspaceOptions,
} from "@/modules/workspace/types";
import { useSessionStore } from "@/store/session";

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

const mode = computed(() => String(route.query.mode ?? "combined"));
const readyAssets = computed(
  () =>
    options.value?.assets.filter(
      (asset) =>
        asset.project_id === projectId.value &&
        asset.processing_status === "ready" &&
        asset.manifest_status === "ready",
    ) ?? [],
);
const hasPendingAssets = computed(
  () =>
    options.value?.assets.some(
      (asset) =>
        asset.project_id === projectId.value &&
        !["ready", "rejected", "deleted"].includes(asset.processing_status),
    ) ?? false,
);
const canSubmit = computed(
  () =>
    !isLoading.value &&
    !isSubmitting.value &&
    selectedAssetIds.value.length > 0 &&
    selectedSkillCodes.value.length > 0 &&
    Boolean(projectId.value && modelId.value && goal.value.trim() && audience.value.trim()),
);

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
        asset.processing_status === "ready" &&
        asset.manifest_status === "ready",
    )
    .slice(0, 1)
    .map((asset) => asset.asset_id);
}

async function loadOptions() {
  isLoading.value = true;
  errorMessage.value = "";
  try {
    const loaded = await workspaceApi.loadOptions(requireToken());
    options.value = loaded;
    applyDefaults(loaded);
  } catch (error) {
    errorMessage.value = readableError(error);
  } finally {
    isLoading.value = false;
  }
}

async function upload(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file || !projectId.value) return;
  isUploading.value = true;
  errorMessage.value = "";
  try {
    await workspaceApi.uploadAsset(
      file,
      projectId.value,
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
            <option v-for="project in options.projects" :key="project.project_id" :value="project.project_id">
              {{ project.name }}
            </option>
          </select>
        </label>
        <div class="asset-list">
          <label v-for="asset in readyAssets" :key="asset.asset_id">
            <input v-model="selectedAssetIds" type="checkbox" :value="asset.asset_id" />
            <span>
              <strong>{{ asset.original_filename }}</strong>
              <small>{{ (asset.byte_size / 1024).toFixed(1) }} KB · 可用于生成</small>
            </span>
          </label>
        </div>
        <p v-if="!readyAssets.length" class="status-note" role="status">
          材料完成安全处理后才能继续。
          <span v-if="hasPendingAssets">当前材料仍在处理，请稍后刷新。</span>
        </p>
        <label class="upload-button">
          <input type="file" :disabled="isUploading || !projectId" @change="upload" />
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

.asset-list label,
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

.asset-list label > span,
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
