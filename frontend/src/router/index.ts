import type { Pinia } from "pinia";
import {
  createRouter,
  createWebHistory,
  type RouterHistory,
} from "vue-router";

import { useSessionStore } from "@/store/session";

import { resolveRouteAccess } from "./permission-guard";
import { routes } from "./routes";

interface RouterOptions {
  history?: RouterHistory;
  pinia: Pinia;
}
export function createOfficeAiRouter(options: RouterOptions) {
  const router = createRouter({
    history: options.history ?? createWebHistory(),
    routes,
  });
  router.beforeEach((to) => {
    const session = useSessionStore(options.pinia);
    return resolveRouteAccess(session, to.meta);
  });
  return router;
}
