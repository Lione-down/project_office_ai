import { apiClient } from "@/api/request";

import type {
  AssetSummary,
  BriefGenerationSelection,
  CreditBalance,
  CreditLedger,
  GeneratedBrief,
  GenerationOutputs,
  GenerationTask,
  ModelSummary,
  ProjectSummary,
  SkillSummary,
  TermLibrarySummary,
  WorkspaceOptions,
  WorkflowTask,
} from "./types";

interface WorkspaceApiClient {
  get<T>(path: string, options?: { accessToken?: string }): Promise<T>;
  post<T>(
    path: string,
    body: unknown,
    options?: { accessToken?: string; headers?: HeadersInit },
  ): Promise<T>;
  postForm<T>(
    path: string,
    body: FormData,
    headers: HeadersInit,
    options?: { accessToken?: string },
  ): Promise<T>;
  delete(path: string, options?: { accessToken?: string }): Promise<void>;
  download(path: string, options?: { accessToken?: string }): Promise<Blob>;
}

export function createWorkspaceApi(client: WorkspaceApiClient) {
  return {
    async loadOptions(accessToken: string): Promise<WorkspaceOptions> {
      const [projects, assets, skills, models, termLibraries] = await Promise.all([
        client.get<ProjectSummary[]>("/projects", { accessToken }),
        client.get<AssetSummary[]>("/assets", { accessToken }),
        client.get<SkillSummary[]>("/skills", { accessToken }),
        client.get<ModelSummary[]>("/models", { accessToken }),
        client.get<TermLibrarySummary[]>("/term-libraries", { accessToken }),
      ]);
      return { projects, assets, skills, models, termLibraries };
    },
    generateBrief(selection: BriefGenerationSelection, accessToken: string) {
      return client.post<GeneratedBrief>("/briefs/generate", selection, {
        accessToken,
      });
    },
    createWorkflowTask(
      selection: BriefGenerationSelection,
      idempotencyKey: string,
      accessToken: string,
    ) {
      return client.post<WorkflowTask>(
        "/workflow-tasks",
        selection,
        {
          accessToken,
          headers: { "Idempotency-Key": idempotencyKey },
        },
      );
    },
    listWorkflowTasks(accessToken: string) {
      return client.get<WorkflowTask[]>("/workflow-tasks", { accessToken });
    },
    getWorkflowTask(taskId: string, accessToken: string) {
      return client.get<WorkflowTask>(`/workflow-tasks/${taskId}`, {
        accessToken,
      });
    },
    createGeneration(
      briefId: string,
      idempotencyKey: string,
      accessToken: string,
    ) {
      return client.post<GenerationTask>(
        "/generations",
        { brief_id: briefId },
        {
          accessToken,
          headers: { "Idempotency-Key": idempotencyKey },
        },
      );
    },
    getGeneration(taskId: string, accessToken: string) {
      return client.get<GenerationTask>(`/generations/${taskId}`, {
        accessToken,
      });
    },
    retryGeneration(taskId: string, accessToken: string) {
      return client.post<GenerationTask>(
        `/generations/${taskId}/retry`,
        {},
        { accessToken },
      );
    },
    getGenerationOutputs(taskId: string, accessToken: string) {
      return client.get<GenerationOutputs>(`/generations/${taskId}/outputs`, {
        accessToken,
      });
    },
    getCreditBalance(accessToken: string) {
      return client.get<CreditBalance>("/credits/balance", { accessToken });
    },
    getCreditLedger(accessToken: string) {
      return client.get<CreditLedger>("/credits/ledger", { accessToken });
    },
    uploadAsset(
      file: File,
      projectId: string | undefined,
      idempotencyKey: string,
      accessToken: string,
    ) {
      const form = new FormData();
      form.set("file", file);
      if (projectId) form.set("project_id", projectId);
      return client.postForm<AssetSummary>(
        "/assets/uploads",
        form,
        { "Idempotency-Key": idempotencyKey },
        { accessToken },
      );
    },
    downloadAsset(assetId: string, accessToken: string) {
      return client.download(`/assets/${assetId}/download`, { accessToken });
    },
    deleteAsset(assetId: string, accessToken: string) {
      return client.delete(`/assets/${assetId}`, { accessToken });
    },
  };
}

export const workspaceApi = createWorkspaceApi(apiClient);
