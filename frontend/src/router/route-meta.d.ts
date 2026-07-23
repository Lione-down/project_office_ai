import "vue-router";

import type { UserRole } from "@/types/access";

declare module "vue-router" {
  interface RouteMeta {
    requiresAuth: boolean;
    shell?: "public" | "user" | "admin";
    roles?: UserRole[];
    loginRoute?: "login" | "admin-login";
    allowDuringPasswordChange?: boolean;
  }
}
