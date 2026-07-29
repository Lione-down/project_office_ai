<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import { deckApi } from "@/modules/decks/api";
import type {
  DeckCreateInput,
  DeckSkillCode,
  DeckSourceMode,
} from "@/modules/decks/types";
import { workspaceApi } from "@/modules/workspace/api";
import type { WorkspaceOptions } from "@/modules/workspace/types";
import { useSessionStore } from "@/store/session";

const route = useRoute();
const router = useRouter();
const session = useSessionStore();
const options = ref<WorkspaceOptions | null>(null);
const isBusy = ref(false);
const error = ref("");
const projectId = ref("");
const modelId = ref(String(route.query.modelId ?? ""));
const topic = ref("");
const audience = ref("");
const slideCount = ref(10);
const style = ref("清晰、专业、适合演示");
const sourceMode = ref<DeckSourceMode>("inspiration");
const skillCode = ref<DeckSkillCode>("ppt.knowledge-education.v1");
const assetIds = ref<string[]>([]);

const messageId = computed(() => String(route.query.messageId ?? ""));
const availableAssets = computed(() =>
  (options.value?.assets ?? []).filter(
    (asset) =>
      asset.project_id === projectId.value &&
      asset.processing_status === "ready" &&
      asset.manifest_status === "valid",
  ),
);
const selectedBytes = computed(() =>
  availableAssets.value
    .filter((asset) => assetIds.value.includes(asset.asset_id))
    .reduce((total, asset) => total + asset.byte_size, 0),
);
const availableSkills = computed(() =>
  (options.value?.skills ?? []).filter(
    (skill) =>
      skill.status === "published" &&
      ["ppt.sales-business-review.v1", "ppt.knowledge-education.v1"].includes(
        skill.skill_code,
      ),
  ),
);
const availableModels = computed(() =>
  (options.value?.models ?? []).filter(
    (model) =>
      model.status === "active" &&
      model.user_visible &&
      model.allowed_skills.includes(skillCode.value),
  ),
);
const canSubmit = computed(
  () =>
    Boolean(
      messageId.value &&
        projectId.value &&
        modelId.value &&
        topic.value.trim() &&
        audience.value.trim(),
    ) &&
    slideCount.value >= 3 &&
    slideCount.value <= 40 &&
    (sourceMode.value === "inspiration" || assetIds.value.length > 0) &&
    assetIds.value.length <= 20 &&
    selectedBytes.value <= 200 * 1024 * 1024,
);

function requireToken() {
  if (!session.accessToken) throw new Error("登录状态已失效");
  return session.accessToken;
}

async function load() {
  try {
    options.value = await workspaceApi.loadOptions(requireToken());
    projectId.value =
      options.value.projects.find((project) => project.is_default)?.project_id ??
      options.value.projects[0]?.project_id ??
      "";
    if (!availableSkills.value.some((skill) => skill.skill_code === skillCode.value)) {
      skillCode.value =
        (availableSkills.value[0]?.skill_code as DeckSkillCode | undefined) ??
        "ppt.sales-business-review.v1";
    }
    if (!availableModels.value.some((model) => model.model_id === modelId.value)) {
      modelId.value =
        availableModels.value.find((model) => model.is_recommended)?.model_id ??
        availableModels.value[0]?.model_id ??
        "";
    }
  } catch {
    error.value = "创建选项加载失败，请稍后重试。";
  }
}

watch(sourceMode, (mode) => {
  if (mode === "inspiration") assetIds.value = [];
});
watch(skillCode, () => {
  if (!availableModels.value.some((model) => model.model_id === modelId.value)) {
    modelId.value = availableModels.value[0]?.model_id ?? "";
  }
});
watch(projectId, () => {
  assetIds.value = [];
});

async function submit() {
  if (!canSubmit.value || isBusy.value) return;
  isBusy.value = true;
  error.value = "";
  const payload: DeckCreateInput = {
    project_id: projectId.value,
    model_id: modelId.value,
    topic: topic.value.trim(),
    audience: audience.value.trim(),
    slide_count: slideCount.value,
    language: "zh-CN",
    style: style.value.trim(),
    source_mode: sourceMode.value,
    skill_code: skillCode.value,
    asset_ids: [...assetIds.value],
  };
  try {
    const created = await deckApi.createDraft(
      messageId.value,
      payload,
      crypto.randomUUID(),
      requireToken(),
    );
    await router.push({
      name: "deck-editor",
      params: { draftId: created.draft_id },
    });
  } catch (caught) {
    error.value =
      caught instanceof Error ? caught.message : "Deck Draft 创建失败";
  } finally {
    isBusy.value = false;
  }
}

onMounted(load);
</script>

<template>
  <main class="deck-create" lang="zh-CN">
    <header>
      <p>Agnes → Deck Studio</p>
      <h1>把这条回复整理为可编辑的 PPT 大纲</h1>
      <span>只接受成功的 assistant message；大纲由用户确认后才进入 Preflight。</span>
    </header>
    <form @submit.prevent="submit">
      <section>
        <h2>目标与结构</h2>
        <label>
          <span>项目</span>
          <select v-model="projectId" required>
            <option
              v-for="project in options?.projects ?? []"
              :key="project.project_id"
              :value="project.project_id"
            >
              {{ project.name }}
            </option>
          </select>
        </label>
        <label><span>主题</span><input v-model="topic" required maxlength="500" /></label>
        <label><span>受众</span><input v-model="audience" required maxlength="500" /></label>
        <div class="two-column">
          <label>
            <span>页数</span>
            <input v-model.number="slideCount" type="number" min="3" max="40" />
          </label>
          <label>
            <span>语言</span>
            <select disabled><option>简体中文（zh-CN）</option></select>
          </label>
        </div>
        <label>
          <span>演示风格</span>
          <input v-model="style" required maxlength="500" />
        </label>
      </section>

      <section>
        <h2>来源、Skill 与模型</h2>
        <fieldset>
          <legend>来源模式</legend>
          <label><input v-model="sourceMode" type="radio" value="inspiration" /> 灵感</label>
          <label><input v-model="sourceMode" type="radio" value="materials" /> 资料</label>
          <label><input v-model="sourceMode" type="radio" value="mixed" /> 混合</label>
        </fieldset>
        <label>
          <span>Skill（由你显式确认）</span>
          <select v-model="skillCode">
            <option
              v-for="skill in availableSkills"
              :key="skill.skill_code"
              :value="skill.skill_code"
            >
              {{ skill.display_name }}
            </option>
          </select>
        </label>
        <label>
          <span>Outline Director 模型</span>
          <select v-model="modelId" required>
            <option
              v-for="model in availableModels"
              :key="model.model_id"
              :value="model.model_id"
            >
              {{ model.display_name }}
            </option>
          </select>
        </label>
        <div v-if="sourceMode !== 'inspiration'" class="asset-picker">
          <p>仅显示当前项目 owner-scoped、ready/valid 的冻结资料。</p>
          <label v-for="asset in availableAssets" :key="asset.asset_id">
            <input v-model="assetIds" type="checkbox" :value="asset.asset_id" />
            {{ asset.original_filename }}
          </label>
          <small>
            已选 {{ assetIds.length }}/20，{{ (selectedBytes / 1024 / 1024).toFixed(1) }}/200 MiB
          </small>
        </div>
      </section>

      <p v-if="error" class="oa-error" role="alert">{{ error }}</p>
      <button type="submit" :disabled="!canSubmit || isBusy">
        {{ isBusy ? "正在整理严格大纲…" : "创建 Deck Draft" }}
      </button>
    </form>
  </main>
</template>

<style scoped>
.deck-create { max-width: 980px; margin: 0 auto; padding: 32px; color: #18202f; }
.deck-create > header { max-width: 720px; margin-bottom: 24px; }
.deck-create > header p { color: #52606d; font-size: 12px; letter-spacing: .08em; text-transform: uppercase; }
form { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
section { padding: 22px; border: 1px solid #dbe1ea; border-radius: 16px; background: #fff; }
label { display: grid; gap: 6px; margin: 13px 0; color: #4f5d70; font-size: 13px; }
input, select { box-sizing: border-box; width: 100%; border: 1px solid #cfd7e2; border-radius: 9px; padding: 10px 12px; background: #fbfcfe; }
fieldset { display: flex; gap: 18px; border: 0; padding: 0; }
fieldset label { display: flex; align-items: center; }
fieldset input, .asset-picker input { width: auto; }
.two-column { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
form > button { grid-column: 1 / -1; min-height: 48px; border: 0; border-radius: 10px; color: #fff; background: #253b80; }
form > button:disabled { opacity: .45; }
.asset-picker { max-height: 220px; overflow: auto; padding: 12px; border-radius: 10px; background: #f5f7fa; }
@media (max-width: 760px) { form { grid-template-columns: 1fr; } }
</style>
