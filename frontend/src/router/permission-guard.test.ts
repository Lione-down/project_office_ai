import { describe, expect, it } from "vitest";

import { resolveRouteAccess } from "./permission-guard";

describe("permission guard", () => {
  it("redirects anonymous users from protected routes", () => {
    expect(
      resolveRouteAccess(
        { isAuthenticated: false, role: null, mustChangePassword: false },
        { requiresAuth: true },
      ),
    ).toEqual({ name: "login" });
  });

  it("uses the dedicated admin login for anonymous admin routes", () => {
    expect(
      resolveRouteAccess(
        { isAuthenticated: false, role: null, mustChangePassword: false },
        { requiresAuth: true, roles: ["admin"], loginRoute: "admin-login" },
      ),
    ).toEqual({ name: "admin-login" });
  });

  it("redirects users without the required role", () => {
    expect(
      resolveRouteAccess(
        { isAuthenticated: true, role: "user", mustChangePassword: false },
        { requiresAuth: true, roles: ["admin"] },
      ),
    ).toEqual({ name: "no-permission" });
  });

  it("does not let a forced-password user bypass the password change route", () => {
    expect(
      resolveRouteAccess(
        { isAuthenticated: true, role: "user", mustChangePassword: true },
        { requiresAuth: true },
      ),
    ).toEqual({ name: "password-change" });

    expect(
      resolveRouteAccess(
        { isAuthenticated: true, role: "user", mustChangePassword: true },
        { requiresAuth: true, allowDuringPasswordChange: true },
      ),
    ).toBe(true);
  });

  it("allows authorized users", () => {
    expect(
      resolveRouteAccess(
        { isAuthenticated: true, role: "admin", mustChangePassword: false },
        { requiresAuth: true, roles: ["admin"] },
      ),
    ).toBe(true);
  });
});
