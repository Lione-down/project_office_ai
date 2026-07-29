<script setup lang="ts">
import { computed, ref } from "vue";

import { deckApi } from "@/modules/decks/api";
import type { DeckSlide, ImageJob } from "@/modules/decks/types";
import type { ModelSummary } from "@/modules/workspace/types";

const props = defineProps<{
  slide: DeckSlide;
  index: number;
  draftId: string;
  draftRevision: number;
  imageModels: ModelSummary[];
  selectedImageModelId: string;
  imageJob?: ImageJob;
  isBusy: boolean;
  accessToken: string | null;
}>();

const emit = defineEmits<{
  "update:selectedImageModelId": [value: string];
  "update:job": [value: ImageJob];
  "update:busy": [value: boolean];
  "update:error": [value: string];
}>();

const isSkipped = ref(false);
const selectedImageModel = computed(() =>
  props.imageModels.find(
    (model) => model.model_id === props.selectedImageModelId,
  ),
);
const status = computed(() => {
  if (isSkipped.value) return "已跳过，不会创建任务或扣费";
  const job = props.imageJob;
  if (!job) return "未创建图片任务";
  if (job.status === "succeeded" && job.output_asset) {
    return `已就绪 · ${job.output_asset.width}×${job.output_asset.height}`;
  }
  if (job.status === "provider_uncertain") return "Provider 结果未知，未自动重试";
  if (job.status === "failed") return job.error_message ?? "图片生成失败";
  return `真实状态：${job.status} · ${job.progress}%`;
});
const visualKindLabel = computed(() => {
  const kind = props.slide.visual_direction?.kind ?? "none";
  return {
    none: "无需视觉",
    diagram: "结构图",
    chart: "图表",
    illustration: "插画",
    photo: "照片",
  }[kind];
});

function requireToken(): string {
  if (!props.accessToken) throw new Error("登录状态已失效");
  return props.accessToken;
}

async function createImage(action: "generate" | "replace" | "regenerate") {
  const direction = props.slide.visual_direction;
  const model = selectedImageModel.value;
  if (!direction || direction.kind === "none" || !model) return;
  const confirmed = window.confirm(
    `确认使用 ${model.display_name} 为“${props.slide.title}”创建图片任务？`,
  );
  if (!confirmed) return;
  emit("update:busy", true);
  emit("update:error", "");
  try {
    const creditPerImage = Number(model.capabilities.credit_per_image ?? 0);
    const next = await deckApi.createImageJob(
      props.draftId,
      {
        expected_revision: props.draftRevision,
        slide_id: props.slide.slide_id,
        action,
        prompt: direction.prompt,
        alt_text: direction.alt_text,
        model_id: model.model_id,
        requested_size: direction.requested_size,
        requested_ratio: direction.requested_ratio,
        crop_mode: direction.crop_mode,
        confirmed: true,
        accepted_estimated_credits: Number.isFinite(creditPerImage)
          ? creditPerImage
          : 0,
        ...(props.imageJob
          ? { supersedes_job_id: props.imageJob.media_job_id }
          : {}),
      },
      crypto.randomUUID(),
      requireToken(),
    );
    isSkipped.value = false;
    emit("update:job", next);
  } catch (caught) {
    emit(
      "update:error",
      caught instanceof Error ? caught.message : "图片任务创建失败",
    );
  } finally {
    emit("update:busy", false);
  }
}
</script>

<template>
  <section class="visual-workbench" :aria-labelledby="`visual-title-${index}`">
    <div class="visual-copy">
      <div class="visual-heading">
        <span :id="`visual-title-${index}`" :data-testid="`visual-kind-${index}`">
          {{ visualKindLabel }}
        </span>
        <small>
          {{ slide.visual_direction?.requested_size }} ·
          {{ slide.visual_direction?.requested_ratio }}
        </small>
      </div>
      <textarea
        v-if="slide.visual_direction?.kind !== 'none'"
        v-model="slide.visual_direction!.prompt"
        class="visual-prompt"
        maxlength="4000"
        aria-label="图片 Prompt"
      />
      <p v-else>Visual Director 建议本页保持留白，不自动创建图片。</p>
    </div>
    <div class="visual-controls">
      <label v-if="slide.visual_direction?.kind !== 'none'">
        <span>图片模型</span>
        <select
          :value="selectedImageModelId"
          :disabled="isBusy"
          @change="emit('update:selectedImageModelId', ($event.target as HTMLSelectElement).value)"
        >
          <option
            v-for="model in imageModels"
            :key="model.model_id"
            :value="model.model_id"
          >
            {{ model.display_name }}
          </option>
        </select>
      </label>
      <div
        class="media-status"
        :data-testid="`slide-image-status-${index}`"
        aria-live="polite"
      >
        {{ status }}
      </div>
      <div
        v-if="slide.visual_direction?.kind !== 'none'"
        class="media-actions"
      >
        <button
          :data-testid="`slide-image-generate-${index}`"
          type="button"
          :disabled="isBusy || !selectedImageModelId || !!imageJob"
          @click="createImage('generate')"
        >
          生成图片
        </button>
        <button
          v-if="imageJob"
          type="button"
          :disabled="isBusy"
          @click="createImage('regenerate')"
        >
          重新生成
        </button>
        <button
          v-if="imageJob"
          type="button"
          :disabled="isBusy"
          @click="createImage('replace')"
        >
          替换
        </button>
        <button
          :data-testid="`slide-image-skip-${index}`"
          type="button"
          :disabled="isBusy"
          @click="isSkipped = true"
        >
          跳过
        </button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.visual-workbench { display: grid; grid-template-columns: minmax(0, 1fr) 280px; gap: 18px; margin-top: 18px; padding-top: 18px; border-top: 1px solid #e2e7ee; }
.visual-copy, .visual-controls { display: grid; gap: 10px; align-content: start; }
.visual-heading { display: flex; justify-content: space-between; gap: 12px; align-items: baseline; }
.visual-heading > span { font-weight: 700; color: #23344d; }
.visual-heading small, .media-status { color: #66758a; font-size: 13px; line-height: 1.6; }
.visual-prompt { width: 100%; box-sizing: border-box; min-height: 112px; resize: vertical; border: 1px solid #cfd7e2; border-radius: 9px; padding: 10px 12px; color: #18202f; background: #fbfcfe; line-height: 1.65; }
.visual-controls label { display: grid; gap: 6px; margin: 12px 0; font-size: 13px; color: #4f5d70; }
.visual-controls select { width: 100%; border: 1px solid #cfd7e2; border-radius: 9px; padding: 10px 12px; background: #fbfcfe; }
.media-status { min-height: 42px; display: flex; align-items: center; padding: 0 11px; border-radius: 8px; background: #f2f5f9; font-variant-numeric: tabular-nums; }
.media-actions { display: flex; flex-wrap: wrap; gap: 8px; }
.media-actions button { min-height: 40px; border: 1px solid #c9d2df; border-radius: 9px; padding: 9px 13px; background: #fff; cursor: pointer; font-size: 14px; }
.media-actions button:disabled { cursor: not-allowed; opacity: .45; }
@media (max-width: 800px) {
  .visual-workbench { grid-template-columns: 1fr; }
}
</style>
