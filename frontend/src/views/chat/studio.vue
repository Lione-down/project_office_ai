<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { RouterLink } from "vue-router";

import { chatApi } from "@/modules/chat/api";
import { markdownToPlainText, renderSafeMarkdown } from "@/modules/chat/safe-markdown";
import { ChatEventReducer } from "@/modules/chat/sse";
import { useChatStore } from "@/modules/chat/store";
import type { ChatMessage, ChatRunRequest } from "@/modules/chat/types";
import { useSessionStore } from "@/store/session";


const session = useSessionStore();
const chat = useChatStore();
const composer = ref("");
const search = ref("");
const selectedModelId = ref("");
const thinkingEnabled = ref(false);
const isStreaming = ref(false);
const activeRunId = ref<string | null>(null);
const streamError = ref<string | null>(null);
const editingMessageId = ref<string | null>(null);
const renameValue = ref("");
const isRenaming = ref(false);

const selectedModel = computed(() =>
  chat.models.find((model) => model.model_id === selectedModelId.value),
);
const canUseThinking = computed(
  () => selectedModel.value?.capabilities.thinking === true,
);
const groupedThreads = computed(() => {
  const groups: Record<string, typeof chat.threads> = {
    今天: [],
    "7 天内": [],
    "30 天内": [],
    更早: [],
  };
  const now = Date.now();
  for (const thread of chat.threads) {
    const age = now - new Date(thread.updated_at).getTime();
    const days = age / 86_400_000;
    const label = days < 1 ? "今天" : days < 7 ? "7 天内" : days < 30 ? "30 天内" : "更早";
    groups[label].push(thread);
  }
  return Object.entries(groups).filter(([, threads]) => threads.length);
});

function recommendedChatModel() {
  return (
    chat.models.find((model) => model.model_code === "agnes-2.5-flash") ??
    chat.models.find((model) => model.is_recommended) ??
    chat.models[0]
  );
}

function requireToken() {
  if (!session.accessToken) throw new Error("登录状态已失效");
  return session.accessToken;
}

function temporaryMessage(
  role: "user" | "assistant",
  content: string,
  status: ChatMessage["status"],
): ChatMessage {
  const messageId = `pending-${crypto.randomUUID()}`;
  return {
    message_id: messageId,
    sequence: chat.messages.length + 1,
    role,
    content,
    status,
    parent_message_id: null,
    supersedes_message_id: null,
    branch_root_id: messageId,
    run_id: null,
    model_code: role === "assistant" ? selectedModel.value?.model_code ?? null : null,
    deck_draft_id: null,
    deck_status: null,
    generation_task_id: null,
    generation_status: null,
    created_at: new Date().toISOString(),
    finalized_at: null,
  };
}

async function loadStudio() {
  await chat.load(requireToken(), search.value);
  const preferred =
    chat.models.find((model) => model.model_id === chat.activeThread?.default_model_id) ??
    recommendedChatModel();
  selectedModelId.value = preferred?.model_id ?? "";
}

async function openThread(threadId: string) {
  if (isStreaming.value) return;
  await chat.open(threadId, requireToken());
  selectedModelId.value = chat.activeThread?.default_model_id ?? chat.models[0]?.model_id ?? "";
  thinkingEnabled.value = false;
  streamError.value = null;
}

async function createThread() {
  const model = recommendedChatModel();
  if (!model) return;
  await chat.create(model.model_id, "chat", requireToken());
  selectedModelId.value = model.model_id;
}

async function selectModel() {
  thinkingEnabled.value = canUseThinking.value ? thinkingEnabled.value : false;
  if (chat.activeThread) {
    await chat.update(
      { default_model_id: selectedModelId.value },
      requireToken(),
    );
  }
}

async function setMode(mode: "chat" | "ppt") {
  if (!chat.activeThread || chat.activeThread.mode === mode) return;
  await chat.update({ mode }, requireToken());
}

async function send(
  overrides: Partial<ChatRunRequest> = {},
) {
  if (!chat.activeThread || !selectedModelId.value || isStreaming.value) return;
  const content = composer.value.trim();
  if (!overrides.regenerate_from_message_id && !content) return;
  streamError.value = null;
  const payload: ChatRunRequest = {
    model_id: selectedModelId.value,
    thinking_enabled: canUseThinking.value && thinkingEnabled.value,
    ...overrides,
  };
  if (!overrides.regenerate_from_message_id) {
    payload.content = content;
    const userMessage = temporaryMessage("user", content, "succeeded");
    if (editingMessageId.value) {
      payload.supersedes_message_id = editingMessageId.value;
      userMessage.supersedes_message_id = editingMessageId.value;
    }
    chat.appendMessage(userMessage);
  }
  const assistant = temporaryMessage("assistant", "", "streaming");
  chat.appendMessage(assistant);
  composer.value = "";
  editingMessageId.value = null;
  isStreaming.value = true;
  const reducer = new ChatEventReducer();
  try {
    await chatApi.streamMessage(
      chat.activeThread.thread_id,
      payload,
      crypto.randomUUID(),
      requireToken(),
      (event) => {
        const state = reducer.apply(event);
        activeRunId.value = state.runId;
        const assistantId =
          typeof event.payload.assistant_message_id === "string"
            ? event.payload.assistant_message_id
            : assistant.message_id;
        if (assistantId !== assistant.message_id) {
          assistant.message_id = assistantId;
        }
        chat.patchMessage(assistant.message_id, {
          content: state.content,
          status: state.status === "idle" ? "streaming" : state.status,
          run_id: state.runId,
        });
      },
    );
  } catch {
    chat.patchMessage(assistant.message_id, {
      status: "failed",
      content: assistant.content,
    });
    streamError.value = "回复生成失败，未切换模型或自动重试。";
  } finally {
    isStreaming.value = false;
    activeRunId.value = null;
  }
}

async function stop() {
  if (!activeRunId.value) return;
  await chatApi.cancelRun(activeRunId.value, requireToken());
}

function editAndResend(message: ChatMessage) {
  composer.value = message.content;
  editingMessageId.value = message.message_id;
}

async function copyMessage(message: ChatMessage) {
  await navigator.clipboard.writeText(markdownToPlainText(message.content));
}

function isHighRisk(content: string) {
  return /(医学|医疗|诊断|用药|法律|诉讼|投资|证券|金融建议)/u.test(content);
}

async function saveRename() {
  const title = renameValue.value.trim();
  if (!title) return;
  await chat.update({ title }, requireToken());
  isRenaming.value = false;
}

async function deleteCurrentThread() {
  await chat.remove(requireToken());
  selectedModelId.value = chat.activeThread?.default_model_id ?? chat.models[0]?.model_id ?? "";
}

onMounted(loadStudio);
</script>

<template>
  <section class="chat-studio" lang="zh-CN">
    <aside class="thread-rail" aria-label="AI 创作会话">
      <button class="oa-button oa-button--primary new-thread" type="button" @click="createThread">
        开启新对话
      </button>
      <label class="thread-search">
        <span class="sr-only">搜索会话</span>
        <input
          v-model="search"
          class="oa-input"
          type="search"
          placeholder="搜索会话"
          @change="loadStudio"
        />
      </label>
      <p v-if="chat.isLoading" class="thread-state" role="status">正在加载会话…</p>
      <div v-else-if="chat.error" class="thread-state thread-state--error" role="alert">
        <span>{{ chat.error }}</span>
        <button type="button" @click="loadStudio">重试</button>
      </div>
      <nav v-else class="thread-groups" aria-label="会话历史">
        <section v-for="[label, threads] in groupedThreads" :key="label">
          <h2>{{ label }}</h2>
          <button
            v-for="thread in threads"
            :key="thread.thread_id"
            type="button"
            :class="{ active: chat.activeThread?.thread_id === thread.thread_id }"
            @click="openThread(thread.thread_id)"
          >
            <strong>{{ thread.title }}</strong>
            <span>{{ thread.model_code }}</span>
          </button>
        </section>
      </nav>
    </aside>

    <main class="conversation">
      <header class="conversation-header">
        <div>
          <p>AI 创作中心</p>
          <div v-if="isRenaming" class="rename-row">
            <input v-model="renameValue" class="oa-input" maxlength="200" aria-label="会话标题" />
            <button type="button" @click="saveRename">保存</button>
            <button type="button" @click="isRenaming = false">取消</button>
          </div>
          <h1 v-else>{{ chat.activeThread?.title ?? "开始一段新对话" }}</h1>
        </div>
        <div v-if="chat.activeThread" class="thread-actions">
          <button
            type="button"
            @click="renameValue = chat.activeThread?.title ?? ''; isRenaming = true"
          >
            重命名
          </button>
          <button type="button" class="danger-action" @click="deleteCurrentThread">删除</button>
        </div>
      </header>

      <section v-if="!chat.activeThread" class="conversation-empty">
        <strong>从一个问题开始</strong>
        <p>选择已发布的 Agnes 模型，回复会持续保存到当前账号。</p>
        <button class="oa-button oa-button--primary" type="button" @click="createThread">
          开启新对话
        </button>
      </section>

      <template v-else>
        <section class="messages" aria-live="polite">
          <article
            v-for="message in chat.messages"
            :key="message.message_id"
            class="message"
            :class="`message--${message.role}`"
          >
            <header>
              <strong>{{ message.role === "user" ? "你" : message.model_code ?? "Agnes" }}</strong>
              <span v-if="message.status === 'streaming'">正在生成</span>
              <span v-else-if="message.status === 'cancelled_partial'">已停止，保留部分内容</span>
              <span v-else-if="message.status === 'provider_uncertain'">Provider 结果未知</span>
              <span v-else-if="message.status === 'failed'">生成失败</span>
            </header>
            <div
              v-if="message.role === 'assistant'"
              class="markdown-body"
              v-html="renderSafeMarkdown(message.content)"
            />
            <p v-else class="user-content">{{ message.content }}</p>
            <p
              v-if="message.role === 'assistant' && isHighRisk(message.content)"
              class="unverified-warning"
              data-testid="unverified-warning"
            >
              AI 生成，尚未核验。请勿直接作为医学、法律或金融决策依据。
            </p>
            <footer v-if="message.status !== 'streaming'">
              <button type="button" @click="copyMessage(message)">复制</button>
              <RouterLink
                v-if="message.role === 'assistant' && message.status === 'succeeded'"
                class="deck-action"
                :data-testid="`create-deck-${message.message_id}`"
                :to="{
                  name: message.deck_draft_id ? 'deck-editor' : 'deck-create',
                  params: message.deck_draft_id
                    ? { draftId: message.deck_draft_id }
                    : undefined,
                  query: message.deck_draft_id
                    ? undefined
                    : {
                        messageId: message.message_id,
                        modelId: selectedModelId,
                      },
                }"
              >
                {{ message.deck_draft_id ? "打开 PPT 大纲" : "整理为 PPT 大纲" }}
              </RouterLink>
              <button
                v-if="message.role === 'user'"
                type="button"
                @click="editAndResend(message)"
              >
                编辑后重发
              </button>
              <button
                v-else
                :data-testid="`regenerate-${message.message_id}`"
                type="button"
                @click="send({ regenerate_from_message_id: message.message_id })"
              >
                重新生成
              </button>
            </footer>
          </article>
          <p v-if="streamError" class="oa-error" role="alert">{{ streamError }}</p>
        </section>

        <section class="composer-panel">
          <div class="composer-controls">
            <div class="mode-switch" aria-label="创作模式">
              <button
                type="button"
                :aria-pressed="chat.activeThread.mode === 'chat'"
                @click="setMode('chat')"
              >
                普通对话
              </button>
              <button
                type="button"
                :aria-pressed="chat.activeThread.mode === 'ppt'"
                @click="setMode('ppt')"
              >
                PPT 创作
              </button>
            </div>
            <label>
              <span class="sr-only">选择模型</span>
              <select
                v-model="selectedModelId"
                data-testid="chat-model"
                :disabled="isStreaming"
                @change="selectModel"
              >
                <option
                  v-for="model in chat.models"
                  :key="model.model_id"
                  :value="model.model_id"
                >
                  {{ model.display_name }}
                </option>
              </select>
            </label>
            <label v-if="canUseThinking" class="thinking-toggle" data-testid="chat-thinking">
              <input v-model="thinkingEnabled" type="checkbox" :disabled="isStreaming" />
              Thinking
            </label>
          </div>
          <label class="composer">
            <span class="sr-only">输入消息</span>
            <textarea
              v-model="composer"
              data-testid="chat-composer"
              maxlength="32768"
              :disabled="isStreaming"
              :placeholder="editingMessageId ? '编辑内容后发送，将创建新分支' : '输入问题，Shift + Enter 换行'"
              @keydown.ctrl.enter.prevent="send()"
              @keydown.meta.enter.prevent="send()"
            />
            <button
              v-if="isStreaming"
              type="button"
              class="composer-action composer-action--stop"
              data-testid="chat-stop"
              @click="stop"
            >
              停止
            </button>
            <button
              v-else
              type="button"
              class="composer-action"
              data-testid="chat-send"
              :disabled="!composer.trim()"
              @click="send()"
            >
              发送
            </button>
          </label>
          <p>Chat 首期不读取文件或 Web，内容可能不准确。Ctrl / ⌘ + Enter 发送。</p>
        </section>
      </template>
    </main>
  </section>
</template>

<style scoped src="./studio.css"></style>
