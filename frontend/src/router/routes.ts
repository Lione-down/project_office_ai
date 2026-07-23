import type { RouteRecordRaw } from "vue-router";

import SystemView from "@/views/system-view.vue";
import BriefConfirmView from "@/views/brief/confirm.vue";

export const routes: RouteRecordRaw[] = [
  {
    path: "/login",
    name: "login",
    component: SystemView,
    meta: { requiresAuth: false },
  },
  {
    path: "/",
    name: "home",
    component: SystemView,
    meta: { requiresAuth: true },
  },
  {
    path: "/admin",
    name: "admin",
    component: SystemView,
    meta: { requiresAuth: true, roles: ["admin"] },
  },
  {
    path: "/briefs/:briefId/confirm",
    name: "brief-confirm",
    component: BriefConfirmView,
    meta: { requiresAuth: true },
  },
];
