<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { ApiError } from "@/api/request";
import { deckApi } from "@/modules/decks/api";
import type {
  DeckBrief,
  DeckDraft,
  DeckSlide,
  ImageJob,
  MediaJob,
  VideoJob,
} from "@/modules/decks/types";
import type { ModelSummary, TemplateSummary } from "@/modules/workspace/types";
import {
  compatibleTemplateOptions,
  safeTemplatePreviewUrl,
} from "@/modules/templates/template-catalog";
import { useSessionStore } from "@/store/session";
import SlideVisualWorkbench from "@/views/deck/components/slide-visual-workbench.vue";
import SlideVideoWorkbench from "@/views/deck/components/slide-video-workbench.vue";

const route = useRoute();
const router = useRouter();
const session = useSessionStore();
const draft = ref<DeckDraft | null>(null);
const content = ref<DeckBrief | null>(null);
const isBusy = ref(false);
const error = ref("");
const isStale = ref(false);
const templates = ref<TemplateSummary[]>([]);
const selectedTemplateCode = ref("");
const models = ref<ModelSummary[]>([]);
const selectedImageModelId = ref("");
const selectedVideoModelId = ref("");
let mediaPollTimer: number | undefined;

const draftId = computed(() => String(route.params.draftId));
const estimatedCredits = computed(
  () => draft.value?.preflight_snapshot?.estimated_credits ?? null,
);
const compatibleTemplates = computed(() =>
  compatibleTemplateOptions(
    templates.value,
    content.value?.skill_code ?? "",
  ),
);
const selectedTemplate = computed(() =>
  compatibleTemplates.value.find(
    (template) => template.template_code === selectedTemplateCode.value,
  ),
);
const imageModels = computed(() =>
  models.value.filter(
    (model) =>
      model.status === "active" &&
      model.user_visible &&
      model.capabilities.image_generation === true,
  ),
);
const videoModels = computed(() =>
  models.value.filter(
    (model) =>
      model.status === "active" &&
      model.user_visible &&
      model.capabilities.video_generation === true,
  ),
);
function cloneContract<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

function requireToken() {
  if (!session.accessToken) throw new Error("登录状态已失效");
  return session.accessToken;
}

function replaceDraft(next: DeckDraft) {
  draft.value = next;
  content.value = cloneContract(next.content);
  selectedTemplateCode.value = next.template_snapshot?.template_code ?? "";
  error.value = "";
  isStale.value = false;
}

async function load() {
  isBusy.value = true;
  try {
    const token = requireToken();
    const [nextDraft, nextTemplates, nextModels] = await Promise.all([
      deckApi.getDraft(draftId.value, token),
      deckApi.listTemplates(token),
      deckApi.listModels(token),
    ]);
    templates.value = nextTemplates;
    models.value = nextModels;
    const recommended =
      imageModels.value.find((model) => model.is_recommended) ?? imageModels.value[0];
    selectedImageModelId.value = recommended?.model_id ?? "";
    const recommendedVideo =
      videoModels.value.find((model) => model.is_recommended) ??
      videoModels.value[0];
    selectedVideoModelId.value = recommendedVideo?.model_id ?? "";
    replaceDraft(nextDraft);
  } catch {
    error.value = "Deck Draft 加载失败，请稍后重试。";
  } finally {
    isBusy.value = false;
  }
}

function imageJobForSlide(slideId: string): ImageJob | undefined {
  return [...(draft.value?.media_jobs ?? [])]
    .reverse()
    .find((job): job is ImageJob => job.slide_id === slideId && job.kind === "image");
}

function videoJobForSlide(slideId: string): VideoJob | undefined {
  return [...(draft.value?.media_jobs ?? [])]
    .reverse()
    .find((job): job is VideoJob => job.slide_id === slideId && job.kind === "video");
}

function upsertMediaJob(next: MediaJob) {
  if (!draft.value) return;
  const jobs = draft.value.media_jobs ?? [];
  const index = jobs.findIndex((job) => job.media_job_id === next.media_job_id);
  if (index === -1) jobs.push(next);
  else jobs.splice(index, 1, next);
}

async function pollMediaJobs() {
  const active = (draft.value?.media_jobs ?? []).filter((job) =>
    ["queued", "submitted", "running"].includes(job.status),
  );
  if (!active.length || !session.accessToken) return;
  const updates = await Promise.all(
    active.map((job) => deckApi.getMediaJob(job.media_job_id, session.accessToken!)),
  );
  updates.forEach(upsertMediaJob);
}

function moveSlide(index: number, offset: number) {
  if (!content.value) return;
  const nextIndex = index + offset;
  if (nextIndex < 0 || nextIndex >= content.value.slides.length) return;
  const [slide] = content.value.slides.splice(index, 1);
  content.value.slides.splice(nextIndex, 0, slide);
}

function duplicateSlide(index: number) {
  if (!content.value || content.value.slides.length >= 40) return;
  const copy = cloneContract(content.value.slides[index]);
  copy.slide_id = crypto.randomUUID();
  copy.title = `${copy.title}（副本）`;
  copy.provenance = [{ kind: "user_input", evidence_ids: [] }];
  content.value.slides.splice(index + 1, 0, copy);
}

function deleteSlide(index: number) {
  if (!content.value || content.value.slides.length <= 3) return;
  content.value.slides.splice(index, 1);
}

function addSlide() {
  if (!content.value || content.value.slides.length >= 40) return;
  const slide: DeckSlide = {
    slide_id: crypto.randomUUID(),
    title: "新页面",
    purpose: "说明本页目标",
    body: ["填写本页要点"],
    speaker_notes: "",
    visual_suggestion: "",
    provenance: [{ kind: "user_input", evidence_ids: [] }],
  };
  content.value.slides.push(slide);
}

async function run(action: () => Promise<DeckDraft>) {
  if (isBusy.value) return;
  isBusy.value = true;
  error.value = "";
  try {
    replaceDraft(await action());
  } catch (caught) {
    if (caught instanceof ApiError && caught.code === "deck_revision_stale") {
      isStale.value = true;
      error.value = "Draft 已被更新，请刷新后再继续。";
    } else {
      error.value = caught instanceof Error ? caught.message : "操作失败";
    }
  } finally {
    isBusy.value = false;
  }
}

async function save() {
  if (!draft.value || !content.value) return;
  const expectedRevision = draft.value.revision;
  const nextContent = cloneContract(content.value);
  await run(() =>
    deckApi.updateDraft(
      draftId.value,
      {
        expected_revision: expectedRevision,
        content: nextContent,
        template_code: selectedTemplateCode.value,
      },
      requireToken(),
    ),
  );
}

async function confirm() {
  if (!draft.value) return;
  await run(() =>
    deckApi.confirmDraft(
      draftId.value,
      {
        expected_revision: draft.value!.revision,
        high_risk_confirmed: false,
      },
      requireToken(),
    ),
  );
}

async function preflight() {
  await run(() => deckApi.preflightDraft(draftId.value, requireToken()));
}

async function generate() {
  if (!draft.value || estimatedCredits.value === null || isBusy.value) return;
  isBusy.value = true;
  error.value = "";
  try {
    const task = await deckApi.generate(
      draftId.value,
      {
        expected_revision: draft.value.revision,
        accepted_estimated_credits: estimatedCredits.value,
      },
      crypto.randomUUID(),
      requireToken(),
    );
    await router.push({
      name: "generation-detail",
      params: { taskId: task.task_id },
    });
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "生成任务创建失败";
  } finally {
    isBusy.value = false;
  }
}

onMounted(async () => {
  await load();
  mediaPollTimer = window.setInterval(() => {
    void pollMediaJobs();
  }, 2000);
});
onBeforeUnmount(() => {
  if (mediaPollTimer !== undefined) window.clearInterval(mediaPollTimer);
});
</script>

<template>
  <main class="deck-editor" lang="zh-CN">
    <header class="deck-header">
      <div>
        <p class="eyebrow">Deck Studio · Revision {{ draft?.revision ?? "—" }}</p>
        <h1>{{ content?.topic ?? "正在加载 Deck Draft" }}</h1>
        <p v-if="content">{{ content.audience }} · {{ content.skill_code }}</p>
      </div>
      <div class="header-actions">
        <button data-testid="deck-save" type="button" :disabled="isBusy" @click="save">
          保存新 Revision
        </button>
        <button data-testid="deck-confirm" type="button" :disabled="isBusy" @click="confirm">
          确认大纲
        </button>
        <button
          data-testid="deck-preflight"
          type="button"
          :disabled="isBusy || draft?.status === 'draft'"
          @click="preflight"
        >
          运行 Preflight
        </button>
      </div>
    </header>

    <section v-if="isStale" class="stale-gate" data-testid="deck-stale" role="alert">
      <strong>Draft 已被更新</strong>
      <span>当前页面不会覆盖较新的 revision。</span>
      <button data-testid="deck-reload" type="button" @click="load">刷新 Draft</button>
    </section>
    <p v-else-if="error" class="oa-error" role="alert">{{ error }}</p>

    <section v-if="content" class="deck-grid">
      <article class="template-selector">
        <div>
          <span>认证模板</span>
          <select
            v-model="selectedTemplateCode"
            data-testid="deck-template-select"
            :disabled="isBusy"
          >
            <option
              v-for="template in compatibleTemplates"
              :key="template.template_code"
              :value="template.template_code"
            >
              {{ template.name }} · v{{ template.version }}
            </option>
          </select>
          <small>切换后保存会创建新的不可变 Revision。</small>
        </div>
        <img
          v-if="selectedTemplate"
          data-testid="deck-template-preview"
          :src="safeTemplatePreviewUrl(selectedTemplate.cover_url)"
          :alt="`${selectedTemplate.name}静态预览`"
        />
      </article>
      <article
        v-for="(slide, index) in content.slides"
        :key="slide.slide_id"
        class="slide-card"
        data-testid="slide-card"
      >
        <header>
          <span>{{ String(index + 1).padStart(2, "0") }}</span>
          <div class="slide-actions">
            <button
              :data-testid="`slide-up-${index}`"
              type="button"
              :disabled="index === 0"
              @click="moveSlide(index, -1)"
            >
              上移
            </button>
            <button
              :data-testid="`slide-down-${index}`"
              type="button"
              :disabled="index === content.slides.length - 1"
              @click="moveSlide(index, 1)"
            >
              下移
            </button>
            <button
              :data-testid="`slide-duplicate-${index}`"
              type="button"
              @click="duplicateSlide(index)"
            >
              复制
            </button>
            <button
              :data-testid="`slide-delete-${index}`"
              type="button"
              :disabled="content.slides.length <= 3"
              @click="deleteSlide(index)"
            >
              删除
            </button>
          </div>
        </header>
        <label>
          <span>标题</span>
          <input v-model="slide.title" data-testid="slide-title" maxlength="200" />
        </label>
        <label>
          <span>本页目标</span>
          <textarea v-model="slide.purpose" maxlength="500" />
        </label>
        <label>
          <span>正文要点（每行一条）</span>
          <textarea
            :value="slide.body.join('\n')"
            @input="slide.body = ($event.target as HTMLTextAreaElement).value.split('\n').filter(Boolean)"
          />
        </label>
        <div class="slide-meta">
          <label>
            <span>讲者备注</span>
            <textarea v-model="slide.speaker_notes" maxlength="4000" />
          </label>
          <label>
            <span>视觉建议</span>
            <textarea v-model="slide.visual_suggestion" maxlength="1000" />
          </label>
        </div>
        <SlideVisualWorkbench
          v-if="slide.visual_direction"
          :slide="slide"
          :index="index"
          :draft-id="draftId"
          :draft-revision="draft?.revision ?? 0"
          :image-models="imageModels"
          :selected-image-model-id="selectedImageModelId"
          :image-job="imageJobForSlide(slide.slide_id)"
          :is-busy="isBusy"
          :access-token="session.accessToken"
          @update:selected-image-model-id="selectedImageModelId = $event"
          @update:job="upsertMediaJob"
          @update:busy="isBusy = $event"
          @update:error="error = $event"
        />
        <SlideVideoWorkbench
          :slide="slide"
          :index="index"
          :draft-id="draftId"
          :draft-revision="draft?.revision ?? 0"
          :video-models="videoModels"
          :selected-video-model-id="selectedVideoModelId"
          :video-job="videoJobForSlide(slide.slide_id)"
          :is-busy="isBusy"
          :access-token="session.accessToken"
          @update:selected-video-model-id="selectedVideoModelId = $event"
          @update:job="upsertMediaJob"
          @update:busy="isBusy = $event"
          @update:error="error = $event"
        />
      </article>
      <button class="add-slide" type="button" @click="addSlide">+ 添加页面</button>
    </section>

    <footer v-if="draft?.preflight_snapshot" class="generation-bar">
      <div>
        <strong>
          {{ draft.preflight_snapshot.has_blockers ? "Preflight 有阻断" : "Preflight 已通过" }}
        </strong>
        <span>预计 {{ draft.preflight_snapshot.estimated_credits }} Credits</span>
      </div>
      <button
        data-testid="deck-generate"
        type="button"
        :disabled="draft.preflight_snapshot.has_blockers || isBusy"
        @click="generate"
      >
        创建 PPTX 生成任务
      </button>
    </footer>
  </main>
</template>

<style scoped>
.deck-editor { max-width: 1240px; margin: 0 auto; padding: 28px; color: var(--oa-text, #18202f); }
.deck-header, .generation-bar { display: flex; justify-content: space-between; gap: 24px; align-items: center; }
.deck-header { padding: 24px; border: 1px solid #dbe1ea; border-radius: 18px; background: #fff; }
.eyebrow { color: #52606d; font-size: 12px; letter-spacing: .08em; text-transform: uppercase; }
.header-actions, .slide-actions { display: flex; flex-wrap: wrap; gap: 8px; }
button { border: 1px solid #c9d2df; border-radius: 9px; padding: 9px 13px; background: #fff; cursor: pointer; }
button:disabled { cursor: not-allowed; opacity: .45; }
.deck-grid { display: grid; gap: 18px; margin: 22px 0 96px; }
.template-selector { display: grid; grid-template-columns: minmax(0, 1fr) minmax(280px, 420px); gap: 24px; align-items: center; padding: 22px; border: 1px solid #dbe1ea; border-radius: 16px; background: #fff; }
.template-selector > div { display: grid; gap: 10px; }
.template-selector select { width: 100%; border: 1px solid #cfd7e2; border-radius: 9px; padding: 10px 12px; background: #fbfcfe; }
.template-selector img { width: 100%; border: 1px solid #dbe1ea; border-radius: 10px; }
.slide-card { padding: 22px; border: 1px solid #dbe1ea; border-radius: 16px; background: #fff; box-shadow: 0 8px 24px rgb(21 35 56 / 5%); }
.slide-card > header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.slide-card label { display: grid; gap: 6px; margin: 12px 0; font-size: 13px; color: #4f5d70; }
input, textarea { width: 100%; box-sizing: border-box; border: 1px solid #cfd7e2; border-radius: 9px; padding: 10px 12px; color: #18202f; background: #fbfcfe; }
textarea { min-height: 76px; resize: vertical; }
.slide-meta { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.add-slide { min-height: 72px; border-style: dashed; }
.stale-gate { display: flex; gap: 14px; align-items: center; margin: 16px 0; padding: 14px; border-radius: 12px; background: #fff4df; }
.generation-bar { position: sticky; bottom: 16px; padding: 16px 20px; border: 1px solid #ced8e5; border-radius: 14px; background: rgb(255 255 255 / 96%); box-shadow: 0 12px 32px rgb(21 35 56 / 14%); }
.generation-bar div { display: grid; gap: 4px; }
@media (max-width: 800px) {
  .deck-header, .generation-bar { align-items: stretch; flex-direction: column; }
  .slide-meta { grid-template-columns: 1fr; }
  .template-selector { grid-template-columns: 1fr; }
}
</style>
