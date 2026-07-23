import { describe, expect, it, vi } from "vitest";

import { createBriefApi } from "./api";


describe("Brief API", () => {
  it("keeps preflight separate from confirmation", async () => {
    const client = {
      get: vi.fn().mockResolvedValue({ revision: 1 }),
      patch: vi.fn().mockResolvedValue({ revision: 2 }),
      post: vi
        .fn()
        .mockResolvedValueOnce({ status: "preflight" })
        .mockResolvedValueOnce({ status: "queued" }),
    };
    const api = createBriefApi(client);

    await api.getBrief("brief-id", "access-token");
    await api.reviseBrief(
      "brief-id",
      { expected_revision: 1, goal: "季度复盘" },
      "access-token",
    );
    await api.preflight("brief-id", "access-token");
    await api.confirm("brief-id", 800, "access-token");

    expect(client.get).toHaveBeenCalledWith("/briefs/brief-id", {
      accessToken: "access-token",
    });
    expect(client.patch).toHaveBeenCalledWith(
      "/briefs/brief-id",
      { expected_revision: 1, goal: "季度复盘" },
      { accessToken: "access-token" },
    );
    expect(client.post).toHaveBeenNthCalledWith(
      1,
      "/generations/preflight",
      { brief_id: "brief-id" },
      { accessToken: "access-token" },
    );
    expect(client.post).toHaveBeenNthCalledWith(
      2,
      "/briefs/brief-id/confirm",
      { accepted_estimated_credits: 800 },
      { accessToken: "access-token" },
    );
  });
});
