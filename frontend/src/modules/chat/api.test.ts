import { describe, expect, it, vi } from "vitest";

import { createChatApi } from "./api";


function sseResponse(chunks: string[], failure?: Error): Response {
  let index = 0;
  return {
    ok: true,
    status: 200,
    headers: new Headers(),
    body: {
      getReader() {
        return {
          async read() {
            if (index < chunks.length) {
              return {
                value: new TextEncoder().encode(chunks[index++]),
                done: false,
              };
            }
            if (failure) throw failure;
            return { value: undefined, done: true };
          },
        };
      },
    },
  } as unknown as Response;
}

function frame(
  event: string,
  sequence: number,
  payload: Record<string, unknown>,
) {
  return [
    `event: ${event}`,
    `id: run-1:${sequence}`,
    `data: ${JSON.stringify({
      schema_version: "chat-sse.v1",
      event,
      run_id: "run-1",
      thread_id: "thread-1",
      sequence,
      occurred_at: "2026-07-29T10:00:00Z",
      trace_id: "trace-1",
      payload,
    })}`,
    "",
    "",
  ].join("\n");
}

describe("chat streaming transport", () => {
  it("resumes once with Last-Event-ID after an interrupted response", async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(
        sseResponse(
          [frame("run.started", 1, {})],
          new TypeError("connection reset"),
        ),
      )
      .mockResolvedValueOnce(
        sseResponse([
          frame("message.snapshot", 2, { content: "已恢复" }),
          frame("run.completed", 3, { content: "已恢复" }),
        ]),
      );
    const client = {
      get: vi.fn(),
      post: vi.fn(),
      patch: vi.fn(),
      delete: vi.fn(),
    };
    const received: string[] = [];

    await createChatApi(client, fetchMock, "http://api.test/api/v1")
      .streamMessage(
        "thread-1",
        { content: "继续", model_id: "model-1", thinking_enabled: false },
        "idem-1",
        "access",
        (event) => received.push(`${event.event}:${event.sequence}`),
      );

    expect(received).toEqual([
      "run.started:1",
      "message.snapshot:2",
      "run.completed:3",
    ]);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls[1]).toEqual([
      "http://api.test/api/v1/chat/runs/run-1/stream",
      expect.objectContaining({
        method: "GET",
        headers: expect.objectContaining({
          Authorization: "Bearer access",
          "Last-Event-ID": "run-1:1",
        }),
      }),
    ]);
  });
});
