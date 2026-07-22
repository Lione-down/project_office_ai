import { describe, expect, it } from "vitest";

import { resolveRouteAccess } from "./permission-guard";

describe("permission guard", () => {
  it("redirects anonymous users from protected routes", () => {
    expect(
      resolveRouteAccess(
        { isAuthenticated: false, role: null },
        { requiresAuth: true },
      ),
    ).toEqual({ name: "login" });
  });

  it("redirects users without the required role", () => {
    expect(
      resolveRouteAccess(
        { isAuthenticated: true, role: "user" },
        { requiresAuth: true, roles: ["admin"] },
      ),
    ).toEqual({ name: "home" });
  });

  it("allows authorized users", () => {
    expect(
      resolveRouteAccess(
        { isAuthenticated: true, role: "admin" },
        { requiresAuth: true, roles: ["admin"] },
      ),
    ).toBe(true);
  });
});
