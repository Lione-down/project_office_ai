import { describe, expect, it, vi } from "vitest";

import { ApiError, createApiClient } from "./request";

describe("API client", () => {
  it("joins the base URL and returns JSON", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "live" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const client = createApiClient({
      baseUrl: "http://localhost:8000/api/v1/",
      fetchImpl,
    });

    const payload = await client.get<{ status: string }>("/health/live");

    expect(payload).toEqual({ status: "live" });
    expect(fetchImpl).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/health/live",
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("maps the stable backend error envelope to ApiError", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          error: {
            error_code: "service_not_ready",
            message: "服务依赖尚未就绪",
            trace_id: "trace-ready",
          },
        }),
        {
          status: 503,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );
    const client = createApiClient({ baseUrl: "/api/v1", fetchImpl });

    const error = await client.get("/health/ready").catch((reason) => reason);

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      code: "service_not_ready",
      message: "服务依赖尚未就绪",
      traceId: "trace-ready",
      status: 503,
    });
  });
});
