import { describe, expect, it, vi } from "vitest";

import { createWorkspaceApi } from "./api";

describe("Workspace API", () => {
  it("keeps selection, Brief generation, task creation, and outputs explicit", async () => {
    const client = {
      get: vi.fn().mockResolvedValue([]),
      post: vi.fn().mockResolvedValue({ brief_id: "brief-id" }),
      postForm: vi.fn().mockResolvedValue({ asset_id: "asset-id" }),
      delete: vi.fn().mockResolvedValue(undefined),
      download: vi.fn().mockResolvedValue(new Blob(["output"])),
    };
    const api = createWorkspaceApi(client);
    const selection = {
      project_id: "project-id",
      asset_ids: ["asset-id"],
      term_library_versions: [],
      skill_codes: [
        "ppt.sales-business-review.v1",
        "excel.sales-analysis-dashboard.v1",
      ],
      model_id: "model-id",
      goal: "季度经营复盘",
      audience: "销售管理层",
      must_include: [],
      must_exclude: [],
    };

    await api.loadOptions("access");
    await api.generateBrief(selection, "access");
    await api.createGeneration("brief-id", "generation-key", "access");
    await api.getGeneration("task-id", "access");
    await api.getGenerationOutputs("task-id", "access");
    await api.getCreditBalance("access");
    await api.getCreditLedger("access");
    await api.downloadAsset("asset-id", "access");
    await api.deleteAsset("asset-id", "access");

    expect(client.post).toHaveBeenCalledWith(
      "/briefs/generate",
      selection,
      { accessToken: "access" },
    );
    expect(client.post).toHaveBeenCalledWith(
      "/generations",
      { brief_id: "brief-id" },
      {
        accessToken: "access",
        headers: { "Idempotency-Key": "generation-key" },
      },
    );
    expect(client.get).toHaveBeenCalledWith("/generations/task-id/outputs", {
      accessToken: "access",
    });
    expect(client.get).toHaveBeenCalledWith("/credits/balance", {
      accessToken: "access",
    });
    expect(client.get).toHaveBeenCalledWith("/credits/ledger", {
      accessToken: "access",
    });
    expect(client.download).toHaveBeenCalledWith(
      "/assets/asset-id/download",
      { accessToken: "access" },
    );
    expect(client.delete).toHaveBeenCalledWith(
      "/assets/asset-id",
      { accessToken: "access" },
    );
  });

  it("uploads one file with the selected project and an idempotency key", async () => {
    const client = {
      get: vi.fn(),
      post: vi.fn(),
      postForm: vi.fn().mockResolvedValue({ asset_id: "asset-id" }),
      delete: vi.fn(),
      download: vi.fn(),
    };
    const api = createWorkspaceApi(client);
    const file = new File(["sales"], "sales.csv", { type: "text/csv" });

    await api.uploadAsset(file, "project-id", "upload-key", "access");

    const [path, form, headers, options] = client.postForm.mock.calls[0];
    expect(path).toBe("/assets/uploads");
    expect(form.get("file")).toBe(file);
    expect(form.get("project_id")).toBe("project-id");
    expect(headers).toEqual({ "Idempotency-Key": "upload-key" });
    expect(options).toEqual({ accessToken: "access" });
  });

  it("omits project_id when uploading the first file without a project", async () => {
    const client = {
      get: vi.fn(),
      post: vi.fn(),
      postForm: vi.fn().mockResolvedValue({ asset_id: "asset-id" }),
      delete: vi.fn(),
      download: vi.fn(),
    };
    const api = createWorkspaceApi(client);
    const file = new File(["sales"], "sales.csv", { type: "text/csv" });

    await api.uploadAsset(file, undefined, "upload-key", "access");

    const [, form] = client.postForm.mock.calls[0];
    expect(form.get("file")).toBe(file);
    expect(form.has("project_id")).toBe(false);
  });
});
