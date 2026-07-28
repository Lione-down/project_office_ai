import { describe, expect, it } from "vitest";

import { routes } from "./routes";

describe("application routes", () => {
  it("maps every approved UI V1 surface to an explicit route", () => {
    const routeNames = routes.map((route) => route.name);

    expect(routeNames).toEqual(
      expect.arrayContaining([
        "login",
        "register",
        "admin-login",
        "home",
        "chat-studio",
        "workflow-new",
        "brief-confirm",
        "generation-detail",
        "workflow-task-detail",
        "tasks",
        "files",
        "templates",
        "term-libraries",
        "credits",
        "password-change",
        "admin-overview",
        "admin-users",
        "admin-invites",
        "admin-providers",
        "admin-credentials",
        "admin-models",
        "admin-tasks",
        "admin-assets",
        "admin-credits",
        "admin-audit-logs",
        "no-permission",
        "not-found",
      ]),
    );
  });

  it("keeps admin surfaces role protected and user surfaces authenticated", () => {
    const byName = new Map(routes.map((route) => [route.name, route]));

    expect(byName.get("admin-overview")?.meta).toMatchObject({
      requiresAuth: true,
      roles: ["admin"],
      shell: "admin",
      loginRoute: "admin-login",
    });
    expect(byName.get("generation-detail")?.meta).toMatchObject({
      requiresAuth: true,
      shell: "user",
    });
    expect(byName.get("workflow-task-detail")?.meta).toMatchObject({
      requiresAuth: true,
      shell: "user",
    });
    expect(byName.get("chat-studio")?.meta).toMatchObject({
      requiresAuth: true,
      shell: "user",
    });
    expect(byName.get("password-change")?.meta).toMatchObject({
      requiresAuth: true,
      allowDuringPasswordChange: true,
    });
    expect(
      byName.get("no-permission")?.meta?.allowDuringPasswordChange,
    ).not.toBe(true);
  });
});
