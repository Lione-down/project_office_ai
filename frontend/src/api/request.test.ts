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

  it("keeps proxy and download failures stable when the body is not JSON", async () => {
    const fetchImpl = vi
      .fn()
      .mockResolvedValueOnce(
        new Response("<html>bad gateway</html>", {
          status: 502,
          headers: { "X-Trace-ID": "proxy-trace" },
        }),
      )
      .mockResolvedValueOnce(new Response(null, { status: 503 }));
    const client = createApiClient({ baseUrl: "/api/v1", fetchImpl });

    const requestError = await client.get("/projects").catch((error) => error);
    const downloadError = await client
      .download("/assets/asset-id/download")
      .catch((error) => error);

    expect(requestError).toMatchObject({
      code: "request_failed",
      message: "请求失败",
      traceId: "proxy-trace",
      status: 502,
    });
    expect(downloadError).toMatchObject({
      code: "request_failed",
      message: "请求失败",
      status: 503,
    });
  });

  it("sends authenticated JSON writes without leaking the token into the body", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ revision: 2 }), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const client = createApiClient({ baseUrl: "/api/v1", fetchImpl });

    await client.patch(
      "/briefs/brief-id",
      { expected_revision: 1, goal: "季度复盘" },
      { accessToken: "access-token" },
    );

    expect(fetchImpl).toHaveBeenCalledOnce();
    const [url, request] = fetchImpl.mock.calls[0];
    const headers = new Headers(request.headers);
    expect(url).toBe("/api/v1/briefs/brief-id");
    expect(request.method).toBe("PATCH");
    expect(headers.get("Authorization")).toBe("Bearer access-token");
    expect(headers.get("Content-Type")).toBe("application/json");
    expect(request.body).toBe(
      JSON.stringify({ expected_revision: 1, goal: "季度复盘" }),
    );
  });

  it("supports authenticated form uploads without setting a multipart boundary", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ asset_id: "asset-id" }), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const client = createApiClient({ baseUrl: "/api/v1", fetchImpl });
    const form = new FormData();
    form.set("file", new File(["sales"], "sales.csv", { type: "text/csv" }));

    await client.postForm(
      "/assets/uploads",
      form,
      { "Idempotency-Key": "upload-key" },
      { accessToken: "access-token" },
    );

    const [, request] = fetchImpl.mock.calls[0];
    const headers = new Headers(request.headers);
    expect(headers.get("Authorization")).toBe("Bearer access-token");
    expect(headers.get("Idempotency-Key")).toBe("upload-key");
    expect(headers.has("Content-Type")).toBe(false);
    expect(request.body).toBe(form);
  });

  it("handles empty deletes and authenticated binary downloads", async () => {
    const fetchImpl = vi
      .fn()
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
      .mockResolvedValueOnce(
        new Response("xlsx", {
          status: 200,
          headers: { "Content-Type": "application/octet-stream" },
        }),
      );
    const client = createApiClient({ baseUrl: "/api/v1", fetchImpl });

    await expect(
      client.delete("/assets/asset-id", { accessToken: "access-token" }),
    ).resolves.toBeUndefined();
    const blob = await client.download("/assets/asset-id/download", {
      accessToken: "access-token",
    });

    expect(blob.size).toBe(4);
    expect(fetchImpl).toHaveBeenCalledTimes(2);
  });
});
