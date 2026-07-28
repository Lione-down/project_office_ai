import { ApiError, apiClient } from "@/api/request";
import { getApiBaseUrl } from "@/utils/runtime-config";

import { createSseParser } from "./sse";
import type {
  ChatModel,
  ChatRunRequest,
  ChatSseEvent,
  ChatThread,
  ChatThreadDetail,
} from "./types";


interface ChatApiClient {
  get<T>(path: string, options?: { accessToken?: string }): Promise<T>;
  post<T>(
    path: string,
    body: unknown,
    options?: { accessToken?: string; headers?: HeadersInit },
  ): Promise<T>;
  patch<T>(
    path: string,
    body: unknown,
    options?: { accessToken?: string; headers?: HeadersInit },
  ): Promise<T>;
  delete(
    path: string,
    options?: { accessToken?: string; headers?: HeadersInit },
  ): Promise<void>;
}

async function streamError(response: Response): Promise<ApiError> {
  try {
    const payload = (await response.json()) as {
      error?: { error_code?: string; message?: string; trace_id?: string };
    };
    return new ApiError(
      payload.error?.error_code ?? "chat_stream_failed",
      payload.error?.message ?? "对话请求失败",
      payload.error?.trace_id ?? response.headers.get("X-Trace-ID"),
      response.status,
    );
  } catch {
    return new ApiError(
      "chat_stream_failed",
      "对话请求失败",
      response.headers.get("X-Trace-ID"),
      response.status,
    );
  }
}

const TERMINAL_EVENTS = new Set([
  "run.completed",
  "run.cancelled_partial",
  "run.failed",
  "run.provider_uncertain",
]);

interface StreamProgress {
  runId: string | null;
  lastSequence: number;
  isTerminal: boolean;
}

async function consumeStream(
  response: Response,
  onEvent: (event: ChatSseEvent) => void,
): Promise<StreamProgress> {
  if (!response.ok) throw await streamError(response);
  if (!response.body) {
    throw new ApiError(
      "chat_stream_unavailable",
      "浏览器未提供流式响应",
      response.headers.get("X-Trace-ID"),
      response.status,
    );
  }
  const progress: StreamProgress = {
    runId: null,
    lastSequence: 0,
    isTerminal: false,
  };
  const parser = createSseParser((event) => {
    progress.runId = event.run_id;
    progress.lastSequence = Math.max(progress.lastSequence, event.sequence);
    progress.isTerminal = TERMINAL_EVENTS.has(event.event);
    onEvent(event);
  });
  const decoder = new TextDecoder();
  const reader = response.body.getReader();
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      parser.push(decoder.decode(value, { stream: true }));
    }
    parser.push(decoder.decode());
    parser.finish();
  } catch (error) {
    if (error instanceof Error) {
      (
        error as Error & { streamProgress?: StreamProgress }
      ).streamProgress = progress;
    }
    throw error;
  }
  return progress;
}

export function createChatApi(
  client: ChatApiClient,
  fetchImpl: typeof fetch = fetch,
  baseUrl = getApiBaseUrl(),
) {
  const normalizedBaseUrl = baseUrl.replace(/\/$/, "");
  return {
    async listModels(accessToken: string): Promise<ChatModel[]> {
      const models = await client.get<ChatModel[]>("/models", { accessToken });
      return models.filter(
        (model) =>
          model.status === "active" &&
          model.capabilities.chat_stream === true &&
          ["agnes-2.5-flash", "agnes-2.0-flash"].includes(model.model_code),
      );
    },
    listThreads(accessToken: string, search = "") {
      const query = search ? `?search=${encodeURIComponent(search)}` : "";
      return client.get<ChatThread[]>(`/chat/threads${query}`, { accessToken });
    },
    getThread(threadId: string, accessToken: string) {
      return client.get<ChatThreadDetail>(`/chat/threads/${threadId}`, {
        accessToken,
      });
    },
    createThread(modelId: string, mode: "chat" | "ppt", accessToken: string) {
      return client.post<ChatThread>(
        "/chat/threads",
        { model_id: modelId, mode },
        {
          accessToken,
          headers: { "Idempotency-Key": crypto.randomUUID() },
        },
      );
    },
    updateThread(
      threadId: string,
      changes: Partial<Pick<ChatThread, "title" | "default_model_id" | "mode">>,
      accessToken: string,
    ) {
      return client.patch<ChatThread>(
        `/chat/threads/${threadId}`,
        changes,
        {
          accessToken,
          headers: { "Idempotency-Key": crypto.randomUUID() },
        },
      );
    },
    deleteThread(threadId: string, accessToken: string) {
      return client.delete(`/chat/threads/${threadId}`, {
        accessToken,
        headers: { "Idempotency-Key": crypto.randomUUID() },
      });
    },
    cancelRun(runId: string, accessToken: string) {
      return client.post(
        `/chat/runs/${runId}/cancel`,
        {},
        {
          accessToken,
          headers: { "Idempotency-Key": crypto.randomUUID() },
        },
      );
    },
    async streamMessage(
      threadId: string,
      payload: ChatRunRequest,
      idempotencyKey: string,
      accessToken: string,
      onEvent: (event: ChatSseEvent) => void,
    ): Promise<void> {
      const response = await fetchImpl(
        `${normalizedBaseUrl}/chat/threads/${threadId}/messages:stream`,
        {
          method: "POST",
          headers: {
            Accept: "text/event-stream",
            Authorization: `Bearer ${accessToken}`,
            "Content-Type": "application/json",
            "Idempotency-Key": idempotencyKey,
          },
          body: JSON.stringify(payload),
        },
      );
      let progress: StreamProgress = {
        runId: null,
        lastSequence: 0,
        isTerminal: false,
      };
      try {
        progress = await consumeStream(response, onEvent);
      } catch (error) {
        const snapshot = (
          error as Error & { streamProgress?: StreamProgress }
        ).streamProgress;
        progress = snapshot ?? progress;
        if (!progress.runId) throw error;
      }
      if (progress.isTerminal) return;
      if (!progress.runId) {
        throw new ApiError(
          "chat_stream_incomplete",
          "流式响应在运行标识建立前中断",
          response.headers.get("X-Trace-ID"),
          response.status,
        );
      }
      const resumed = await fetchImpl(
        `${normalizedBaseUrl}/chat/runs/${progress.runId}/stream`,
        {
          method: "GET",
          headers: {
            Accept: "text/event-stream",
            Authorization: `Bearer ${accessToken}`,
            "Last-Event-ID": `${progress.runId}:${progress.lastSequence}`,
          },
        },
      );
      const resumedProgress = await consumeStream(resumed, onEvent);
      if (!resumedProgress.isTerminal) {
        throw new ApiError(
          "chat_stream_incomplete",
          "恢复后的流式响应未到达终态",
          resumed.headers.get("X-Trace-ID"),
          resumed.status,
        );
      }
    },
  };
}

export const chatApi = createChatApi(apiClient);
