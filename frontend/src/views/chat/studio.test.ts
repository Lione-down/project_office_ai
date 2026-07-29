import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createMemoryHistory, createRouter } from "vue-router";

import { useSessionStore } from "@/store/session";

import ChatStudioView from "./studio.vue";


const chatMocks = vi.hoisted(() => ({
  listModels: vi.fn(),
  listThreads: vi.fn(),
  createThread: vi.fn(),
  getThread: vi.fn(),
  updateThread: vi.fn(),
  deleteThread: vi.fn(),
  streamMessage: vi.fn(),
  cancelRun: vi.fn(),
}));

vi.mock("@/modules/chat/api", () => ({
  chatApi: chatMocks,
}));

const model25 = {
  model_id: "model-25",
  model_code: "agnes-2.5-flash",
  display_name: "Agnes 2.5 Flash",
  capabilities: { chat_stream: true, thinking: true },
  is_recommended: false,
  status: "active",
};
const model20 = {
  model_id: "model-20",
  model_code: "agnes-2.0-flash",
  display_name: "Agnes 2.0 Flash",
  capabilities: { chat_stream: true, thinking: false },
  is_recommended: true,
  status: "active",
};
const thread = {
  thread_id: "thread-1",
  user_id: "user-1",
  title: "季度经营叙事",
  default_model_id: "model-25",
  model_code: "agnes-2.5-flash",
  mode: "chat",
  status: "active",
  last_activity_at: "2026-07-29T10:00:00Z",
  created_at: "2026-07-29T10:00:00Z",
  updated_at: "2026-07-29T10:00:00Z",
};

async function mountStudio() {
  const pinia = createPinia();
  setActivePinia(pinia);
  useSessionStore().setTokens({
    access_token: "access",
    refresh_token: "refresh",
    token_type: "bearer",
  });
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/chat", name: "chat-studio", component: ChatStudioView },
      {
        path: "/decks/new",
        name: "deck-create",
        component: { template: "<div />" },
      },
      { path: "/", component: { template: "<div />" } },
    ],
  });
  await router.push("/chat");
  await router.isReady();
  const wrapper = mount(ChatStudioView, {
    global: { plugins: [pinia, router] },
  });
  await flushPromises();
  return wrapper;
}

describe("AI creation chat studio", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    chatMocks.listModels.mockResolvedValue([model25, model20]);
    chatMocks.listThreads.mockResolvedValue([thread]);
    chatMocks.getThread.mockResolvedValue({ ...thread, messages: [] });
    chatMocks.createThread.mockResolvedValue(thread);
    chatMocks.updateThread.mockResolvedValue(thread);
    chatMocks.deleteThread.mockResolvedValue(undefined);
    chatMocks.cancelRun.mockResolvedValue(undefined);
    chatMocks.streamMessage.mockImplementation(
      async (_threadId, _payload, _key, _token, onEvent) => {
        onEvent({
          schema_version: "chat-sse.v1",
          event: "run.started",
          run_id: "run-1",
          thread_id: "thread-1",
          sequence: 1,
          occurred_at: "2026-07-29T10:00:01Z",
          trace_id: "trace-1",
          payload: {
            user_message_id: "user-message-1",
            assistant_message_id: "assistant-message-1",
          },
        });
        onEvent({
          schema_version: "chat-sse.v1",
          event: "message.delta",
          run_id: "run-1",
          thread_id: "thread-1",
          sequence: 2,
          occurred_at: "2026-07-29T10:00:02Z",
          trace_id: "trace-1",
          payload: { delta: "医学建议仅供参考" },
        });
        onEvent({
          schema_version: "chat-sse.v1",
          event: "run.completed",
          run_id: "run-1",
          thread_id: "thread-1",
          sequence: 3,
          occurred_at: "2026-07-29T10:00:03Z",
          trace_id: "trace-1",
          payload: { content: "医学建议仅供参考" },
        });
      },
    );
  });

  it("loads persistent history and exposes both explicit model choices", async () => {
    const wrapper = await mountStudio();

    expect(chatMocks.listThreads).toHaveBeenCalledWith("access", "");
    expect(chatMocks.getThread).toHaveBeenCalledWith("thread-1", "access");
    const options = wrapper.findAll("[data-testid='chat-model'] option");
    expect(options.map((option) => option.text())).toEqual([
      "Agnes 2.5 Flash",
      "Agnes 2.0 Flash",
    ]);
    const modelSelect = wrapper.get(
      "[data-testid='chat-model']",
    ).element as HTMLSelectElement;
    expect(modelSelect.value).toBe("model-25");
    expect(wrapper.text()).toContain("季度经营叙事");
  });

  it("recommends 2.5 for a new chat without changing the global 2.0 default", async () => {
    chatMocks.listThreads.mockResolvedValue([]);
    const wrapper = await mountStudio();

    await wrapper.get(".new-thread").trigger("click");

    expect(chatMocks.createThread).toHaveBeenCalledWith(
      "model-25",
      "chat",
      "access",
    );
  });

  it("streams a message, renders the terminal reply, and shows high-risk warning", async () => {
    const wrapper = await mountStudio();

    await wrapper.get("[data-testid='chat-composer']").setValue("请给出医学培训结构");
    await wrapper.get("[data-testid='chat-send']").trigger("click");
    await flushPromises();

    expect(chatMocks.streamMessage).toHaveBeenCalledWith(
      "thread-1",
      expect.objectContaining({
        content: "请给出医学培训结构",
        model_id: "model-25",
        thinking_enabled: false,
      }),
      expect.any(String),
      "access",
      expect.any(Function),
    );
    expect(wrapper.text()).toContain("医学建议仅供参考");
    expect(wrapper.get("[data-testid='unverified-warning']").text()).toContain(
      "AI 生成，尚未核验",
    );
    expect(wrapper.get("[data-testid='chat-send']").text()).toContain("发送");
  });

  it("hides Thinking for a model without the published capability", async () => {
    const wrapper = await mountStudio();
    await wrapper.get("[data-testid='chat-model']").setValue("model-20");

    expect(wrapper.find("[data-testid='chat-thinking']").exists()).toBe(false);
  });

  it("regenerates as a new branch without editing the prior assistant message", async () => {
    chatMocks.getThread.mockResolvedValue({
      ...thread,
      messages: [
        {
          message_id: "assistant-old",
          sequence: 2,
          role: "assistant",
          content: "旧回复",
          status: "succeeded",
          parent_message_id: "user-old",
          supersedes_message_id: null,
          branch_root_id: "user-old",
          run_id: "run-old",
          model_code: "agnes-2.5-flash",
          created_at: "2026-07-29T10:00:00Z",
          finalized_at: "2026-07-29T10:00:01Z",
        },
      ],
    });
    const wrapper = await mountStudio();

    await wrapper.get("[data-testid='regenerate-assistant-old']").trigger("click");
    await flushPromises();

    expect(chatMocks.streamMessage).toHaveBeenCalledWith(
      "thread-1",
      expect.objectContaining({
        regenerate_from_message_id: "assistant-old",
        model_id: "model-25",
      }),
      expect.any(String),
      "access",
      expect.any(Function),
    );
    expect(wrapper.text()).toContain("旧回复");
  });

  it("offers Deck conversion only for a successful assistant message", async () => {
    chatMocks.getThread.mockResolvedValue({
      ...thread,
      messages: [
        {
          message_id: "assistant-deck",
          sequence: 2,
          role: "assistant",
          content: "可整理的回复",
          status: "succeeded",
          parent_message_id: "user-old",
          supersedes_message_id: null,
          branch_root_id: "user-old",
          run_id: "run-old",
          model_code: "agnes-2.5-flash",
          created_at: "2026-07-29T10:00:00Z",
          finalized_at: "2026-07-29T10:00:01Z",
        },
      ],
    });
    const wrapper = await mountStudio();

    const link = wrapper.get("[data-testid='create-deck-assistant-deck']");
    expect(link.text()).toContain("PPT 大纲");
    expect(link.attributes("href")).toContain(
      "/decks/new?messageId=assistant-deck",
    );
  });

  it("cancels the active run without discarding its partial content", async () => {
    let finishStream: (() => void) | undefined;
    chatMocks.streamMessage.mockImplementation(
      async (_threadId, _payload, _key, _token, onEvent) => {
        onEvent({
          schema_version: "chat-sse.v1",
          event: "run.started",
          run_id: "run-cancel",
          thread_id: "thread-1",
          sequence: 1,
          occurred_at: "2026-07-29T10:00:01Z",
          trace_id: "trace-cancel",
          payload: { assistant_message_id: "assistant-cancel" },
        });
        onEvent({
          schema_version: "chat-sse.v1",
          event: "message.delta",
          run_id: "run-cancel",
          thread_id: "thread-1",
          sequence: 2,
          occurred_at: "2026-07-29T10:00:02Z",
          trace_id: "trace-cancel",
          payload: { delta: "保留的片段" },
        });
        await new Promise<void>((resolve) => {
          finishStream = resolve;
        });
      },
    );
    const wrapper = await mountStudio();

    await wrapper.get("[data-testid='chat-composer']").setValue("开始生成");
    void wrapper.get("[data-testid='chat-send']").trigger("click");
    await flushPromises();
    await wrapper.get("[data-testid='chat-stop']").trigger("click");

    expect(chatMocks.cancelRun).toHaveBeenCalledWith("run-cancel", "access");
    expect(wrapper.text()).toContain("保留的片段");
    finishStream?.();
    await flushPromises();
  });
});
