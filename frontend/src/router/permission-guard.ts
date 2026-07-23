import type { RouteLocationRaw, RouteMeta } from "vue-router";

import type { SessionAccessSnapshot } from "@/modules/auth/types";

export function resolveRouteAccess(
  access: SessionAccessSnapshot,
  meta: RouteMeta,
): true | RouteLocationRaw {
  if (meta.requiresAuth && !access.isAuthenticated) {
    return { name: meta.loginRoute ?? "login" };
  }
  if (
    access.isAuthenticated &&
    access.mustChangePassword &&
    !meta.allowDuringPasswordChange
  ) {
    return { name: "password-change" };
  }
  if (meta.roles?.length && (!access.role || !meta.roles.includes(access.role))) {
    return { name: "no-permission" };
  }
  return true;
}
