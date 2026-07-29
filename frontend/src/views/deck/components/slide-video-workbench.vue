<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from "vue";

import { deckApi } from "@/modules/decks/api";
import type { DeckSlide, VideoJob } from "@/modules/decks/types";
import type { ModelSummary } from "@/modules/workspace/types";

const props = defineProps<{
  slide: DeckSlide;
  index: number;
  draftId: string;
  draftRevision: number;
  videoModels: ModelSummary[];
  selectedVideoModelId: string;
  videoJob?: VideoJob;
  isBusy: boolean;
  accessToken: string | null;
}>();

const emit = defineEmits<{
  "update:selectedVideoModelId": [value: string];
  "update:job": [value: VideoJob];
  "update:busy": [value: boolean];
  "update:error": [value: string];
}>();

const prompt = ref(
  props.slide.visual_direction?.prompt || props.slide.visual_suggestion || "",
);
const previewUrl = ref("");
const selectedModel = computed(() =>
  props.videoModels.find(
    (model) => model.model_id === props.selectedVideoModelId,
  ),
);
const status = computed(() => {
  const job = props.videoJob;
  if (!job) return "未创建视频任务";
  if (job.status === "succeeded" && job.output_video) {
    return `已就绪 · ${job.output_video.width}×${job.output_video.height} · ${job.output_video.duration_seconds.toFixed(1)} 秒`;
  }
  if (job.status === "provider_uncertain") {
    return "Provider 结果未知，未自动重试";
  }
  if (job.status === "failed") return job.error_message ?? "视频生成失败";
  return `真实状态：${job.status} · ${job.progress}%`;
});
const isActive = computed(() =>
  ["queued", "submitted", "running"].includes(props.videoJob?.status ?? ""),
);

function requireToken(): string {
  if (!props.accessToken) throw new Error("登录状态已失效");
  return props.accessToken;
}

async function createVideo(action: "generate" | "replace" | "regenerate") {
  const model = selectedModel.value;
  if (!model || !prompt.value.trim()) return;
  if (
    !window.confirm(
      `确认使用 ${model.display_name} 为“${props.slide.title}”创建独立视频任务？`,
    )
  ) {
    return;
  }
  emit("update:busy", true);
  emit("update:error", "");
  try {
    const creditPerSecond = Number(model.capabilities.credit_per_second ?? 0);
    const estimatedCredits = Math.ceil(
      (Number.isFinite(creditPerSecond) ? creditPerSecond : 0) * (81 / 24),
    );
    const next = await deckApi.createVideoJob(
      props.draftId,
      {
        expected_revision: props.draftRevision,
        slide_id: props.slide.slide_id,
        action,
        mode: "text-to-video",
        prompt: prompt.value.trim(),
        negative_prompt: "logos, watermarks, unreadable text",
        model_id: model.model_id,
        width: 1152,
        height: 768,
        num_frames: 81,
        frame_rate: 24,
        confirmed: true,
        accepted_estimated_credits: estimatedCredits,
        embed_requested: false,
        ...(props.videoJob
          ? { supersedes_job_id: props.videoJob.media_job_id }
          : {}),
      },
      crypto.randomUUID(),
      requireToken(),
    );
    emit("update:job", next);
  } catch (caught) {
    emit(
      "update:error",
      caught instanceof Error ? caught.message : "视频任务创建失败",
    );
  } finally {
    emit("update:busy", false);
  }
}

async function cancelVideo() {
  if (!props.videoJob) return;
  emit("update:busy", true);
  try {
    const next = await deckApi.cancelMediaJob(
      props.videoJob.media_job_id,
      requireToken(),
    );
    if (next.kind === "video") emit("update:job", next);
  } catch (caught) {
    emit(
      "update:error",
      caught instanceof Error ? caught.message : "视频任务取消失败",
    );
  } finally {
    emit("update:busy", false);
  }
}

async function previewVideo() {
  if (!props.videoJob?.output_video) return;
  const blob = await deckApi.previewMediaAsset(
    props.videoJob.output_video.asset_id,
    requireToken(),
  );
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value);
  previewUrl.value = URL.createObjectURL(blob);
}

async function downloadVideo() {
  if (!props.videoJob?.output_video) return;
  const blob = await deckApi.downloadMediaAsset(
    props.videoJob.output_video.asset_id,
    requireToken(),
  );
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${props.slide.title}.mp4`;
  anchor.click();
  URL.revokeObjectURL(url);
}

onBeforeUnmount(() => {
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value);
});
</script>

<template>
  <section class="video-workbench" :aria-labelledby="`video-title-${index}`">
    <div class="video-copy">
      <div class="video-heading">
        <span :id="`video-title-${index}`">动态素材</span>
        <small>Text-to-video · 1152×768 · 约 3.4 秒</small>
      </div>
      <textarea
        v-model="prompt"
        maxlength="2000"
        aria-label="视频 Prompt"
        placeholder="描述主体动作、镜头运动、光线和风格"
      />
      <p
        class="fallback-note"
        :data-testid="`slide-video-fallback-${index}`"
      >
        PPTX 当前使用海报帧，独立视频附件可预览和下载。PowerPoint 与 WPS 双 Gate
        通过前不声明内嵌。
      </p>
      <video
        v-if="previewUrl"
        class="video-preview"
        :src="previewUrl"
        controls
        preload="metadata"
      />
    </div>
    <div class="video-controls">
      <label>
        <span>视频模型</span>
        <select
          :value="selectedVideoModelId"
          :disabled="isBusy"
          @change="emit('update:selectedVideoModelId', ($event.target as HTMLSelectElement).value)"
        >
          <option
            v-for="model in videoModels"
            :key="model.model_id"
            :value="model.model_id"
          >
            {{ model.display_name }}
          </option>
        </select>
      </label>
      <div
        class="media-status"
        :data-testid="`slide-video-status-${index}`"
        aria-live="polite"
      >
        {{ status }}
      </div>
      <div class="media-actions">
        <button
          :data-testid="`slide-video-generate-${index}`"
          type="button"
          :disabled="isBusy || !selectedVideoModelId || !!videoJob"
          @click="createVideo('generate')"
        >
          生成视频
        </button>
        <button
          v-if="videoJob && !isActive"
          type="button"
          :disabled="isBusy"
          @click="createVideo('regenerate')"
        >
          重新生成
        </button>
        <button
          v-if="isActive"
          type="button"
          :disabled="isBusy"
          @click="cancelVideo"
        >
          取消任务
        </button>
        <button
          v-if="videoJob?.output_video"
          type="button"
          :disabled="isBusy"
          @click="previewVideo"
        >
          预览
        </button>
        <button
          v-if="videoJob?.output_video"
          type="button"
          :disabled="isBusy"
          @click="downloadVideo"
        >
          下载 MP4
        </button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.video-workbench { display: grid; grid-template-columns: minmax(0, 1fr) 280px; gap: 18px; margin-top: 18px; padding: 18px; border: 1px solid #dbe1ea; border-radius: 12px; background: #f8fafc; }
.video-copy, .video-controls { display: grid; gap: 10px; align-content: start; }
.video-heading { display: flex; justify-content: space-between; gap: 12px; align-items: baseline; }
.video-heading > span { font-weight: 700; color: #23344d; }
.video-heading small, .media-status, .fallback-note { color: #66758a; font-size: 13px; line-height: 1.6; }
textarea { width: 100%; box-sizing: border-box; min-height: 96px; resize: vertical; border: 1px solid #cfd7e2; border-radius: 9px; padding: 10px 12px; color: #18202f; background: #fff; line-height: 1.65; }
.fallback-note { margin: 0; padding-left: 10px; border-left: 3px solid #9aabbe; }
.video-preview { width: 100%; border-radius: 9px; background: #111827; }
.video-controls label { display: grid; gap: 6px; font-size: 13px; color: #4f5d70; }
.video-controls select { width: 100%; border: 1px solid #cfd7e2; border-radius: 9px; padding: 10px 12px; background: #fff; }
.media-status { min-height: 42px; display: flex; align-items: center; padding: 0 11px; border-radius: 8px; background: #eef2f7; font-variant-numeric: tabular-nums; }
.media-actions { display: flex; flex-wrap: wrap; gap: 8px; }
.media-actions button { min-height: 40px; border: 1px solid #c9d2df; border-radius: 9px; padding: 9px 13px; background: #fff; cursor: pointer; font-size: 14px; }
.media-actions button:disabled { cursor: not-allowed; opacity: .45; }
@media (max-width: 800px) {
  .video-workbench { grid-template-columns: 1fr; }
  .video-heading { align-items: flex-start; flex-direction: column; }
}
</style>
