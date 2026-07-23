import { describe, expect, it, vi } from "vitest";

import { createAuthApi } from "./api";

describe("Auth API", () => {
  it("keeps login, registration, current user, and password change contracts explicit", async () => {
    const client = {
      get: vi.fn().mockResolvedValue({ role: "user" }),
      post: vi.fn().mockResolvedValue({ access_token: "access" }),
    };
    const api = createAuthApi(client);

    await api.login("13800138000", "safe-password");
    await api.register("13800138000", "safe-password", "INV-CODE");
    await api.me("access");
    await api.changePassword("old-password", "new-safe-password", "access");

    expect(client.post).toHaveBeenNthCalledWith(1, "/auth/login", {
      phone_number: "13800138000",
      password: "safe-password",
    });
    expect(client.post).toHaveBeenNthCalledWith(2, "/auth/register", {
      phone_number: "13800138000",
      password: "safe-password",
      invite_code: "INV-CODE",
      accepted_terms: true,
    });
    expect(client.get).toHaveBeenCalledWith("/auth/me", {
      accessToken: "access",
    });
    expect(client.post).toHaveBeenNthCalledWith(
      3,
      "/auth/change-password",
      {
        current_password: "old-password",
        new_password: "new-safe-password",
      },
      { accessToken: "access" },
    );
  });

  it("rotates refresh tokens and revokes the authenticated Session on logout", async () => {
    const client = {
      get: vi.fn(),
      post: vi.fn().mockResolvedValue({ access_token: "next-access" }),
    };
    const api = createAuthApi(client);

    await api.refresh("refresh-token");
    await api.logout("access-token");

    expect(client.post).toHaveBeenNthCalledWith(1, "/auth/refresh", {
      refresh_token: "refresh-token",
    });
    expect(client.post).toHaveBeenNthCalledWith(
      2,
      "/auth/logout",
      undefined,
      { accessToken: "access-token" },
    );
  });
});
