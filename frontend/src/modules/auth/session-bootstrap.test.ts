import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useSessionStore } from "@/store/session";

import { bootstrapSession } from "./session-bootstrap";

const authMocks = vi.hoisted(() => ({
  refresh: vi.fn(),
  me: vi.fn(),
}));

vi.mock("./api", () => ({
  authApi: authMocks,
}));

describe("Session bootstrap", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
    setActivePinia(createPinia());
  });

  it("rotates a persisted refresh token before restoring access decisions", async () => {
    sessionStorage.setItem("office-ai.refresh-token", "persisted-refresh");
    authMocks.refresh.mockResolvedValue({
      access_token: "rotated-access",
      refresh_token: "rotated-refresh",
      token_type: "bearer",
    });
    authMocks.me.mockResolvedValue({
      user_id: "user-id",
      phone_country_code: "+86",
      phone_number: "13800138000",
      role: "admin",
      status: "active",
      credit_balance: 8420,
      must_change_password: false,
    });
    const session = useSessionStore();

    await bootstrapSession(session);

    expect(authMocks.refresh).toHaveBeenCalledWith("persisted-refresh");
    expect(authMocks.me).toHaveBeenCalledWith("rotated-access");
    expect(session).toMatchObject({
      isAuthenticated: true,
      role: "admin",
      hasBootstrapped: true,
    });
    expect(sessionStorage.getItem("office-ai.refresh-token")).toBe(
      "rotated-refresh",
    );
  });

  it("clears an invalid persisted Session without blocking public routes", async () => {
    sessionStorage.setItem("office-ai.refresh-token", "invalid-refresh");
    authMocks.refresh.mockRejectedValue(new Error("Session 已失效"));
    const session = useSessionStore();

    await bootstrapSession(session);

    expect(session.isAuthenticated).toBe(false);
    expect(session.hasBootstrapped).toBe(true);
    expect(sessionStorage.getItem("office-ai.refresh-token")).toBeNull();
  });
});
