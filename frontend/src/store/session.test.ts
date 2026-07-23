import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it } from "vitest";

import { useSessionStore } from "./session";

describe("Session store", () => {
  beforeEach(() => {
    sessionStorage.clear();
    setActivePinia(createPinia());
  });

  it("keeps tokens private to the store and exposes only access decisions", () => {
    const session = useSessionStore();

    session.setTokens({
      access_token: "access",
      refresh_token: "refresh",
      token_type: "bearer",
    });
    session.applyCurrentUser({
      user_id: "user-id",
      phone_country_code: "+86",
      phone_number: "13800138000",
      role: "user",
      status: "active",
      credit_balance: 8420,
      must_change_password: true,
    });

    expect(session).toMatchObject({
      isAuthenticated: true,
      role: "user",
      mustChangePassword: true,
      creditBalance: 8420,
    });
    expect(session.accessToken).toBe("access");
    expect(session.refreshToken).toBe("refresh");
    expect(sessionStorage.getItem("office-ai.refresh-token")).toBe("refresh");
  });

  it("clears identity and tokens together", () => {
    const session = useSessionStore();
    session.setTokens({
      access_token: "access",
      refresh_token: "refresh",
      token_type: "bearer",
    });

    session.clearSession();

    expect(session.isAuthenticated).toBe(false);
    expect(session.accessToken).toBeNull();
    expect(session.refreshToken).toBeNull();
    expect(session.role).toBeNull();
    expect(session.mustChangePassword).toBe(false);
    expect(sessionStorage.getItem("office-ai.refresh-token")).toBeNull();
  });

  it("restores only the refresh credential for startup rotation", () => {
    sessionStorage.setItem("office-ai.refresh-token", "persisted-refresh");
    const session = useSessionStore();

    expect(session.restoreRefreshToken()).toBe("persisted-refresh");
    expect(session.refreshToken).toBe("persisted-refresh");
    expect(session.accessToken).toBeNull();
    expect(session.isAuthenticated).toBe(false);
  });
});
