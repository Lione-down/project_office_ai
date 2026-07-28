import { defineStore } from "pinia";
import { computed, ref } from "vue";

import { chatApi } from "./api";
import type {
  ChatMessage,
  ChatModel,
  ChatThread,
  ChatThreadDetail,
} from "./types";


export const useChatStore = defineStore("chat", () => {
  const models = ref<ChatModel[]>([]);
  const threads = ref<ChatThread[]>([]);
  const activeThread = ref<ChatThreadDetail | null>(null);
  const isLoading = ref(false);
  const error = ref<string | null>(null);
  const messages = computed<ChatMessage[]>(
    () => activeThread.value?.messages ?? [],
  );

  async function load(accessToken: string, search = "") {
    isLoading.value = true;
    error.value = null;
    try {
      const [availableModels, availableThreads] = await Promise.all([
        chatApi.listModels(accessToken),
        chatApi.listThreads(accessToken, search),
      ]);
      models.value = availableModels;
      threads.value = availableThreads;
      if (
        activeThread.value &&
        !availableThreads.some(
          (thread) => thread.thread_id === activeThread.value?.thread_id,
        )
      ) {
        activeThread.value = null;
      }
      if (!activeThread.value && availableThreads[0]) {
        await open(availableThreads[0].thread_id, accessToken);
      }
    } catch {
      error.value = "会话加载失败，请重试";
    } finally {
      isLoading.value = false;
    }
  }

  async function open(threadId: string, accessToken: string) {
    activeThread.value = await chatApi.getThread(threadId, accessToken);
  }

  async function create(
    modelId: string,
    mode: "chat" | "ppt",
    accessToken: string,
  ) {
    const created = await chatApi.createThread(modelId, mode, accessToken);
    threads.value = [created, ...threads.value];
    await open(created.thread_id, accessToken);
  }

  async function update(
    changes: Partial<Pick<ChatThread, "title" | "default_model_id" | "mode">>,
    accessToken: string,
  ) {
    if (!activeThread.value) return;
    const updated = await chatApi.updateThread(
      activeThread.value.thread_id,
      changes,
      accessToken,
    );
    const index = threads.value.findIndex(
      (thread) => thread.thread_id === updated.thread_id,
    );
    if (index >= 0) threads.value[index] = updated;
    activeThread.value = {
      ...activeThread.value,
      ...updated,
    };
  }

  async function remove(accessToken: string) {
    if (!activeThread.value) return;
    await chatApi.deleteThread(activeThread.value.thread_id, accessToken);
    threads.value = threads.value.filter(
      (thread) => thread.thread_id !== activeThread.value?.thread_id,
    );
    activeThread.value = null;
    if (threads.value[0]) await open(threads.value[0].thread_id, accessToken);
  }

  function appendMessage(message: ChatMessage) {
    if (!activeThread.value) return;
    activeThread.value.messages = [...activeThread.value.messages, message];
  }

  function patchMessage(messageId: string, changes: Partial<ChatMessage>) {
    if (!activeThread.value) return;
    const message = activeThread.value.messages.find(
      (candidate) => candidate.message_id === messageId,
    );
    if (message) Object.assign(message, changes);
  }

  return {
    models,
    threads,
    activeThread,
    messages,
    isLoading,
    error,
    load,
    open,
    create,
    update,
    remove,
    appendMessage,
    patchMessage,
  };
});
