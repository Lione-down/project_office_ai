import type {
  ChatMessageStatus,
  ChatSseEvent,
  ChatSseEventName,
} from "./types";

export type { ChatSseEvent } from "./types";

const EVENT_NAMES = new Set<ChatSseEventName>([
  "run.started",
  "message.delta",
  "message.snapshot",
  "run.completed",
  "run.cancelled_partial",
  "run.failed",
  "run.provider_uncertain",
]);

export interface ChatStreamState {
  runId: string | null;
  content: string;
  status: "idle" | ChatMessageStatus;
  lastSequence: number;
  errorCode: string | null;
}

export function createSseParser(onEvent: (event: ChatSseEvent) => void) {
  let buffer = "";

  function consumeFrame(frame: string) {
    const fields = new Map<string, string>();
    for (const line of frame.split(/\r?\n/)) {
      const separator = line.indexOf(":");
      if (separator < 0) continue;
      const key = line.slice(0, separator);
      const value = line.slice(separator + 1).trimStart();
      if (key === "data" && fields.has(key)) {
        fields.set(key, `${fields.get(key)}\n${value}`);
      } else {
        fields.set(key, value);
      }
    }
    const eventName = fields.get("event");
    if (!eventName || eventName === "heartbeat") return;
    if (!EVENT_NAMES.has(eventName as ChatSseEventName)) return;
    const rawData = fields.get("data");
    if (!rawData) return;
    const payload = JSON.parse(rawData) as Omit<ChatSseEvent, "event">;
    if (
      payload.schema_version !== "chat-sse.v1" ||
      typeof payload.sequence !== "number" ||
      !payload.run_id ||
      !payload.thread_id
    ) {
      throw new Error("chat_stream_invalid");
    }
    onEvent({
      ...payload,
      event: eventName as ChatSseEventName,
    });
  }

  function drain(final = false) {
    let boundary = buffer.search(/\r?\n\r?\n/);
    while (boundary >= 0) {
      const frame = buffer.slice(0, boundary);
      const separator = buffer.match(/\r?\n\r?\n/)?.[0].length ?? 2;
      buffer = buffer.slice(boundary + separator);
      if (frame.trim()) consumeFrame(frame);
      boundary = buffer.search(/\r?\n\r?\n/);
    }
    if (final && buffer.trim()) {
      consumeFrame(buffer);
      buffer = "";
    }
  }

  return {
    push(chunk: string) {
      buffer += chunk;
      drain();
    },
    finish() {
      drain(true);
    },
  };
}

export class ChatEventReducer {
  readonly state: ChatStreamState = {
    runId: null,
    content: "",
    status: "idle",
    lastSequence: 0,
    errorCode: null,
  };

  apply(event: ChatSseEvent): ChatStreamState {
    if (
      this.state.runId !== null &&
      event.run_id !== this.state.runId
    ) {
      return this.state;
    }
    if (event.sequence <= this.state.lastSequence) return this.state;
    this.state.runId = event.run_id;
    this.state.lastSequence = event.sequence;
    if (event.event === "run.started") {
      this.state.status = "streaming";
    } else if (event.event === "message.delta") {
      this.state.content += String(event.payload.delta ?? "");
    } else if (event.event === "message.snapshot") {
      this.state.content = String(event.payload.content ?? "");
    } else {
      if ("content" in event.payload) {
        this.state.content = String(event.payload.content ?? "");
      }
      this.state.status = {
        "run.completed": "succeeded",
        "run.cancelled_partial": "cancelled_partial",
        "run.failed": "failed",
        "run.provider_uncertain": "provider_uncertain",
      }[event.event] as ChatMessageStatus;
      this.state.errorCode =
        typeof event.payload.error_code === "string"
          ? event.payload.error_code
          : null;
    }
    return this.state;
  }
}
