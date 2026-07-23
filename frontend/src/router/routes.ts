import type { RouteRecordRaw } from "vue-router";

import ChangePasswordView from "@/views/auth/change-password.vue";
import LoginView from "@/views/auth/login.vue";
import RegisterView from "@/views/auth/register.vue";
import AdminOverviewView from "@/views/admin/overview.vue";
import AdminResourceView from "@/views/admin/resource.vue";
import BriefConfirmView from "@/views/brief/confirm.vue";
import GenerationDetailView from "@/views/generation/detail.vue";
import NoPermissionView from "@/views/system/no-permission.vue";
import NotFoundView from "@/views/system/not-found.vue";
import HomeView from "@/views/user/home.vue";
import UserResourceView from "@/views/user/resource.vue";
import WorkflowNewView from "@/views/user/workflow-new.vue";

export const routes: RouteRecordRaw[] = [
  {
    path: "/login",
    name: "login",
    component: LoginView,
    meta: { requiresAuth: false, shell: "public" },
  },
  {
    path: "/register",
    name: "register",
    component: RegisterView,
    meta: { requiresAuth: false, shell: "public" },
  },
  {
    path: "/admin/login",
    name: "admin-login",
    component: LoginView,
    props: { mode: "admin" },
    meta: { requiresAuth: false, shell: "public" },
  },
  {
    path: "/",
    name: "home",
    component: HomeView,
    meta: { requiresAuth: true, shell: "user" },
  },
  {
    path: "/workflow/new",
    name: "workflow-new",
    component: WorkflowNewView,
    meta: { requiresAuth: true, shell: "user" },
  },
  {
    path: "/briefs/:briefId/confirm",
    name: "brief-confirm",
    component: BriefConfirmView,
    meta: { requiresAuth: true, shell: "user" },
  },
  {
    path: "/generations/:taskId",
    name: "generation-detail",
    component: GenerationDetailView,
    meta: { requiresAuth: true, shell: "user" },
  },
  ...[
    ["/tasks", "tasks"],
    ["/files", "files"],
    ["/templates", "templates"],
    ["/term-libraries", "term-libraries"],
    ["/credits", "credits"],
  ].map(
    ([path, name]) =>
      ({
        path,
        name,
        component: UserResourceView,
        props: { section: name },
        meta: { requiresAuth: true, shell: "user" },
      }) satisfies RouteRecordRaw,
  ),
  {
    path: "/password/change",
    name: "password-change",
    component: ChangePasswordView,
    meta: {
      requiresAuth: true,
      shell: "public",
      allowDuringPasswordChange: true,
    },
  },
  {
    path: "/admin",
    name: "admin-overview",
    component: AdminOverviewView,
    meta: {
      requiresAuth: true,
      roles: ["admin"],
      shell: "admin",
      loginRoute: "admin-login",
    },
  },
  ...[
    ["/admin/users", "admin-users", "users"],
    ["/admin/invites", "admin-invites", "invites"],
    ["/admin/providers", "admin-providers", "providers"],
    ["/admin/credentials", "admin-credentials", "credentials"],
    ["/admin/models", "admin-models", "models"],
    ["/admin/tasks", "admin-tasks", "tasks"],
    ["/admin/assets", "admin-assets", "assets"],
    ["/admin/credits", "admin-credits", "credits"],
    ["/admin/audit-logs", "admin-audit-logs", "audit-logs"],
  ].map(
    ([path, name, section]) =>
      ({
        path,
        name,
        component: AdminResourceView,
        props: { section },
        meta: {
          requiresAuth: true,
          roles: ["admin"],
          shell: "admin",
          loginRoute: "admin-login",
        },
      }) satisfies RouteRecordRaw,
  ),
  {
    path: "/no-permission",
    name: "no-permission",
    component: NoPermissionView,
    meta: {
      requiresAuth: true,
      shell: "public",
    },
  },
  {
    path: "/:pathMatch(.*)*",
    name: "not-found",
    component: NotFoundView,
    meta: { requiresAuth: false, shell: "public" },
  },
];
