import type { RouteLocationRaw, RouteMeta } from "vue-router";

import type { SessionAccessSnapshot } from "@/modules/auth/types";

export function resolveRouteAccess(
  access: SessionAccessSnapshot,
  meta: RouteMeta,
): true | RouteLocationRaw {
  if (meta.requiresAuth && !access.isAuthenticated) {
    return { name: "login" };
  }
  if (meta.roles?.length && (!access.role || !meta.roles.includes(access.role))) {
    return { name: "home" };
  }
  return true;
}
