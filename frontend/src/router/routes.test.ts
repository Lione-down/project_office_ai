import { describe, expect, it } from "vitest";

import { routes } from "./routes";

describe("application routes", () => {
  it("declares public, authenticated, and admin route metadata", () => {
    expect(routes).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ name: "login", meta: { requiresAuth: false } }),
        expect.objectContaining({ name: "home", meta: { requiresAuth: true } }),
        expect.objectContaining({
          name: "admin",
          meta: { requiresAuth: true, roles: ["admin"] },
        }),
        expect.objectContaining({
          name: "brief-confirm",
          path: "/briefs/:briefId/confirm",
          meta: { requiresAuth: true },
        }),
      ]),
    );
  });
});
