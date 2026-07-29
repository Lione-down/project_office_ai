import { createHash } from "node:crypto";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { afterEach, describe, expect, it } from "vitest";

import {
  RENDER_REQUEST_SCHEMA_VERSION,
  executeRenderRequest,
} from "../src/worker-contract.js";
import { clonePlan } from "./fixtures/sample-plan.js";

const roots: string[] = [];

afterEach(async () => {
  await Promise.all(roots.splice(0).map((root) => rm(root, { recursive: true })));
});

async function workRoot(): Promise<string> {
  const root = await mkdtemp(join(tmpdir(), "office-ai-ppt-worker-"));
  roots.push(root);
  return root;
}

describe("versioned renderer worker contract", () => {
  it("derives an output key inside WORK_ROOT and returns no absolute path", async () => {
    const root = await workRoot();
    const response = await executeRenderRequest(
      {
        schema_version: RENDER_REQUEST_SCHEMA_VERSION,
        request_id: "019f5000-0000-7000-8000-000000000111",
        plan: clonePlan(),
      },
      root,
    );

    expect(response.status).toBe("succeeded");
    if (response.status === "succeeded") {
      expect(response.output_key).toBe(
        "requests/019f5000-0000-7000-8000-000000000111/presentation.pptx",
      );
      expect(response.output_key).not.toMatch(/^[A-Za-z]:|^\//);
      expect(response.plan_sha256).toMatch(/^[a-f0-9]{64}$/);
      expect(response.template_checksum).toBe(
        "9cad7dfef0257d6ef3d02b6d448f31fd833bf64b24f6fda20b113677069509a5",
      );
    }
  });

  it("returns a stable redacted error without plan, path, or stack", async () => {
    const root = await workRoot();
    const response = await executeRenderRequest(
      {
        schema_version: RENDER_REQUEST_SCHEMA_VERSION,
        request_id: "../escape",
        plan: "render C:\\private\\secret.pptx",
      },
      root,
    );

    expect(response).toEqual({
      schema_version: "ppt-renderer.response.v1",
      request_id: null,
      status: "failed",
      error: {
        code: "render_request_invalid",
        message: "Renderer 请求无效",
        retryable: false,
      },
    });
  });

  it("serializes concurrent replay and repairs a corrupt derived output", async () => {
    const root = await workRoot();
    const request = {
      schema_version: RENDER_REQUEST_SCHEMA_VERSION,
      request_id: "019f5000-0000-7000-8000-000000000112",
      plan: clonePlan(),
    };

    const [first, concurrentReplay] = await Promise.all([
      executeRenderRequest(request, root),
      executeRenderRequest(request, root),
    ]);

    expect(first.status).toBe("succeeded");
    expect(concurrentReplay).toEqual(first);
    if (first.status !== "succeeded") return;

    const output = join(root, ...first.output_key.split("/"));
    await writeFile(output, "corrupt");
    const repaired = await executeRenderRequest(request, root);

    expect(repaired.status).toBe("succeeded");
    if (repaired.status === "succeeded") {
      const bytes = await readFile(output);
      expect(repaired.sha256).toBe(
        createHash("sha256").update(bytes).digest("hex"),
      );
      expect(repaired.byte_size).toBe(bytes.length);
      expect(bytes.length).toBeGreaterThan(1_000);
    }
  });
});
