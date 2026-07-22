import "vue-router";

import type { UserRole } from "@/types/access";

declare module "vue-router" {
  interface RouteMeta {
    requiresAuth: boolean;
    roles?: UserRole[];
  }
}
