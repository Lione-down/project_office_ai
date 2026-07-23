import { describe, expect, it, vi } from "vitest";

import { createAdminApi } from "./api";

describe("Admin API", () => {
  it("loads only the resource endpoints already delivered before T4-001", async () => {
    const client = {
      get: vi.fn().mockResolvedValue([]),
      post: vi.fn().mockResolvedValue({}),
    };
    const api = createAdminApi(client);

    await api.listInvites("access");
    await api.listProviders("access");
    await api.listCredentials("access");
    await api.listModels("access");

    expect(client.get.mock.calls).toEqual([
      ["/admin/invite-codes", { accessToken: "access" }],
      ["/admin/providers", { accessToken: "access" }],
      ["/admin/credentials", { accessToken: "access" }],
      ["/admin/models", { accessToken: "access" }],
    ]);
  });

  it("creates an invite with a no-cache one-time code response", async () => {
    const client = {
      get: vi.fn(),
      post: vi.fn().mockResolvedValue({ code: "INV-ONE-TIME" }),
    };
    const api = createAdminApi(client);

    await api.createInvite(
      {
        max_uses: 20,
        expires_at: "2026-08-31T00:00:00Z",
        registration_credit: 1000,
      },
      "access",
    );

    expect(client.post).toHaveBeenCalledWith(
      "/admin/invite-codes",
      {
        max_uses: 20,
        expires_at: "2026-08-31T00:00:00Z",
        registration_credit: 1000,
      },
      { accessToken: "access" },
    );
  });
});
