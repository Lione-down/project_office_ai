import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { describe, expect, it } from "vitest";
import { createMemoryHistory, createRouter } from "vue-router";

import { useSessionStore } from "@/store/session";

import AppShell from "./app-shell.vue";

async function mountShell(
  shell: "user" | "admin",
  initialPath = shell === "admin" ? "/admin" : "/",
) {
  const pinia = createPinia();
  setActivePinia(pinia);
  const session = useSessionStore();
  session.setTokens({
    access_token: "access",
    refresh_token: "refresh",
    token_type: "bearer",
  });
  session.applyCurrentUser({
    user_id: "user-id",
    phone_country_code: "+86",
    phone_number: "13800138000",
    role: shell === "admin" ? "admin" : "user",
    status: "active",
    credit_balance: 8420,
    must_change_password: false,
  });
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      {
        path: shell === "admin" ? "/admin" : "/",
        name: shell === "admin" ? "admin-overview" : "home",
        component: { template: "<div />" },
        meta: { requiresAuth: true, shell },
      },
      {
        path: "/admin/users",
        component: { template: "<div />" },
        meta: { requiresAuth: true, shell: "admin" },
      },
      {
        path: "/:pathMatch(.*)*",
        component: { template: "<div />" },
        meta: { requiresAuth: true, shell },
      },
    ],
  });
  await router.push(initialPath);
  await router.isReady();
  const wrapper = mount(AppShell, {
    slots: { default: "<section>内容</section>" },
    global: { plugins: [pinia, router] },
  });
  return wrapper;
}

describe("App shell", () => {
  it("uses the approved four-item user navigation", async () => {
    const wrapper = await mountShell("user");

    expect(wrapper.get("[aria-label='用户主导航']").text()).toContain("首页");
    expect(wrapper.get("[aria-label='用户主导航']").text()).toContain("任务");
    expect(wrapper.get("[aria-label='用户主导航']").text()).toContain("文件");
    expect(wrapper.get("[aria-label='用户主导航']").text()).toContain("模板");
  });

  it("uses the complete six-item admin navigation labels", async () => {
    const wrapper = await mountShell("admin");
    const navigation = wrapper.get("[aria-label='管理后台主导航']").text();

    for (const label of [
      "概览",
      "用户与邀请码",
      "服务配置",
      "任务与资产",
      "积分",
      "审计日志",
    ]) {
      expect(navigation).toContain(label);
    }
  });

  it("marks only the matching admin navigation group as active", async () => {
    const wrapper = await mountShell("admin", "/admin/users");
    const activeLinks = wrapper.findAll(
      "[aria-label='管理后台主导航'] a.active",
    );

    expect(activeLinks).toHaveLength(1);
    expect(activeLinks[0].text()).toBe("用户与邀请码");
  });

  it.each([
    ["/admin/invites", "用户与邀请码"],
    ["/admin/credentials", "服务配置"],
    ["/admin/assets", "任务与资产"],
  ])("maps %s to its admin navigation group", async (path, label) => {
    const wrapper = await mountShell("admin", path);
    const activeLinks = wrapper.findAll(
      "[aria-label='管理后台主导航'] a.active",
    );

    expect(activeLinks).toHaveLength(1);
    expect(activeLinks[0].text()).toBe(label);
  });
});
