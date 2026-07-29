import { apiClient } from "@/api/request";

import type {
  DeckCreateInput,
  DeckDraft,
  DeckGenerationResult,
  ImageJob,
  ImageJobCreateInput,
  MediaJob,
  VideoJob,
  VideoJobCreateInput,
  DeckUpdateInput,
} from "./types";
import type { TemplateSummary } from "@/modules/workspace/types";
import type { ModelSummary } from "@/modules/workspace/types";


interface DeckApiClient {
  get<T>(path: string, options?: { accessToken?: string }): Promise<T>;
  post<T>(
    path: string,
    body: unknown,
    options?: { accessToken?: string; headers?: HeadersInit },
  ): Promise<T>;
  patch<T>(
    path: string,
    body: unknown,
    options?: { accessToken?: string },
  ): Promise<T>;
  download(
    path: string,
    options?: { accessToken?: string },
  ): Promise<Blob>;
}

export function createDeckApi(client: DeckApiClient) {
  return {
    createDraft(
      messageId: string,
      payload: DeckCreateInput,
      idempotencyKey: string,
      accessToken: string,
    ) {
      return client.post<DeckDraft>(
        `/chat/messages/${messageId}/deck-drafts`,
        payload,
        {
          accessToken,
          headers: { "Idempotency-Key": idempotencyKey },
        },
      );
    },
    getDraft(draftId: string, accessToken: string) {
      return client.get<DeckDraft>(`/deck-drafts/${draftId}`, { accessToken });
    },
    listTemplates(accessToken: string) {
      return client.get<TemplateSummary[]>("/templates", { accessToken });
    },
    listModels(accessToken: string) {
      return client.get<ModelSummary[]>("/models", { accessToken });
    },
    updateDraft(
      draftId: string,
      payload: DeckUpdateInput,
      accessToken: string,
    ) {
      return client.patch<DeckDraft>(`/deck-drafts/${draftId}`, payload, {
        accessToken,
      });
    },
    confirmDraft(
      draftId: string,
      payload: { expected_revision: number; high_risk_confirmed: boolean },
      accessToken: string,
    ) {
      return client.post<DeckDraft>(
        `/deck-drafts/${draftId}/confirm`,
        payload,
        { accessToken },
      );
    },
    preflightDraft(draftId: string, accessToken: string) {
      return client.post<DeckDraft>(
        `/deck-drafts/${draftId}/preflight`,
        {},
        { accessToken },
      );
    },
    generate(
      draftId: string,
      payload: {
        expected_revision: number;
        accepted_estimated_credits: number;
      },
      idempotencyKey: string,
      accessToken: string,
    ) {
      return client.post<DeckGenerationResult>(
        `/deck-drafts/${draftId}/generations`,
        payload,
        {
          accessToken,
          headers: { "Idempotency-Key": idempotencyKey },
        },
      );
    },
    createImageJob(
      draftId: string,
      payload: ImageJobCreateInput,
      idempotencyKey: string,
      accessToken: string,
    ) {
      return client.post<ImageJob>(
        `/deck-drafts/${draftId}/media/images`,
        payload,
        {
          accessToken,
          headers: { "Idempotency-Key": idempotencyKey },
        },
      );
    },
    getImageJob(jobId: string, accessToken: string) {
      return client.get<ImageJob>(`/media/jobs/${jobId}`, { accessToken });
    },
    createVideoJob(
      draftId: string,
      payload: VideoJobCreateInput,
      idempotencyKey: string,
      accessToken: string,
    ) {
      return client.post<VideoJob>(
        `/deck-drafts/${draftId}/media/videos`,
        payload,
        {
          accessToken,
          headers: { "Idempotency-Key": idempotencyKey },
        },
      );
    },
    getMediaJob(jobId: string, accessToken: string) {
      return client.get<MediaJob>(`/media/jobs/${jobId}`, { accessToken });
    },
    cancelMediaJob(jobId: string, accessToken: string) {
      return client.post<MediaJob>(
        `/media/jobs/${jobId}/cancel`,
        {},
        { accessToken },
      );
    },
    previewMediaAsset(assetId: string, accessToken: string) {
      return client.download(`/assets/${assetId}/preview`, { accessToken });
    },
    downloadMediaAsset(assetId: string, accessToken: string) {
      return client.download(`/assets/${assetId}/download`, { accessToken });
    },
  };
}

export const deckApi = createDeckApi(apiClient);
