import { describe, expect, it } from "vitest";

import {
  ChatEventReducer,
  createSseParser,
  type ChatSseEvent,
} from "./sse";

function event(
  sequence: number,
  name: ChatSseEvent["event"],
  payload: Record<string, unknown>,
): ChatSseEvent {
  return {
    schema_version: "chat-sse.v1",
    run_id: "run-1",
    thread_id: "thread-1",
    sequence,
    occurred_at: "2026-07-29T10:00:00Z",
    trace_id: "trace-1",
    event: name,
    payload,
  };
}

describe("chat SSE", () => {
  it("parses fragmented frames and ignores heartbeat payloads", () => {
    const received: ChatSseEvent[] = [];
    const parser = createSseParser((item) => received.push(item));

    parser.push(
      'event: run.started\nid: run-1:1\ndata: {"schema_version":"chat-sse.v1","run_id":"run-1",',
    );
    parser.push(
      '"thread_id":"thread-1","sequence":1,"occurred_at":"2026-07-29T10:00:00Z","trace_id":"trace-1","payload":{}}\n\n',
    );
    parser.push("event: heartbeat\ndata: {}\n\n");
    parser.finish();

    expect(received).toHaveLength(1);
    expect(received[0].event).toBe("run.started");
  });

  it("deduplicates sequence and replaces partial content from a snapshot", () => {
    const reducer = new ChatEventReducer();

    reducer.apply(event(1, "run.started", {}));
    reducer.apply(event(2, "message.delta", { delta: "旧内容" }));
    reducer.apply(event(2, "message.delta", { delta: "重复内容" }));
    reducer.apply(event(3, "message.snapshot", { content: "权威快照" }));
    reducer.apply(event(4, "message.delta", { delta: "继续" }));
    reducer.apply(event(5, "run.cancelled_partial", { content: "权威快照继续" }));

    expect(reducer.state.content).toBe("权威快照继续");
    expect(reducer.state.status).toBe("cancelled_partial");
    expect(reducer.state.lastSequence).toBe(5);
  });
});
