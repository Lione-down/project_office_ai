import { mkdtemp, rm } from "node:fs/promises";
import type { AddressInfo } from "node:net";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { afterEach, describe, expect, it } from "vitest";

import { createRendererServer } from "../src/server.js";
import { clonePlan } from "./fixtures/sample-plan.js";

const roots: string[] = [];

afterEach(async () => {
  await Promise.all(roots.splice(0).map((root) => rm(root, { recursive: true })));
});

async function withServer<T>(
  action: (baseUrl: string) => Promise<T>,
): Promise<T> {
  const root = await mkdtemp(join(tmpdir(), "office-ai-ppt-http-"));
  roots.push(root);
  const server = createRendererServer({ workRoot: root, maxBodyBytes: 1_000_000 });
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  const address = server.address() as AddressInfo;
  try {
    return await action(`http://127.0.0.1:${address.port}`);
  } finally {
    await new Promise<void>((resolve, reject) =>
      server.close((error) => (error ? reject(error) : resolve())),
    );
  }
}

describe("renderer HTTP worker", () => {
  it("serves health and a successful versioned render response", async () => {
    await withServer(async (baseUrl) => {
      const health = await fetch(`${baseUrl}/health`);
      const response = await fetch(`${baseUrl}/v1/render`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          schema_version: "ppt-renderer.request.v1",
          request_id: "019f5000-0000-7000-8000-000000000112",
          plan: clonePlan(),
        }),
      });
      const body = (await response.json()) as Record<string, unknown>;

      expect(health.status).toBe(200);
      expect(response.status).toBe(200);
      expect(body.status).toBe("succeeded");
      expect(body.output_key).toBe(
        "requests/019f5000-0000-7000-8000-000000000112/presentation.pptx",
      );
      expect(response.headers.get("cache-control")).toBe("no-store");
    });
  });

  it("rejects invalid input without echoing plan, path, or stack", async () => {
    await withServer(async (baseUrl) => {
      const secretMarker = "C:\\private\\customer-secret.pptx";
      const response = await fetch(`${baseUrl}/v1/render`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ plan: secretMarker }),
      });
      const body = await response.text();

      expect(response.status).toBe(422);
      expect(body).not.toContain(secretMarker);
      expect(body).not.toContain("stack");
      expect(body).not.toContain("work");
    });
  });
});
