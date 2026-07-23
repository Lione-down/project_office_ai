import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createMemoryHistory, createRouter } from "vue-router";

import { useSessionStore } from "@/store/session";

import LoginView from "./login.vue";

const authMocks = vi.hoisted(() => ({
  login: vi.fn(),
  me: vi.fn(),
}));

vi.mock("@/modules/auth/api", () => ({
  authApi: authMocks,
}));

async function mountLogin(mode: "user" | "admin" = "user") {
  const pinia = createPinia();
  setActivePinia(pinia);
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/login", name: "login", component: LoginView },
      { path: "/", name: "home", component: { template: "<div />" } },
      { path: "/admin", name: "admin-overview", component: { template: "<div />" } },
      {
        path: "/password/change",
        name: "password-change",
        component: { template: "<div />" },
      },
      { path: "/:pathMatch(.*)*", component: { template: "<div />" } },
    ],
  });
  await router.push("/login");
  await router.isReady();
  const wrapper = mount(LoginView, {
    props: { mode },
    global: { plugins: [pinia, router] },
  });
  return { wrapper, router, session: useSessionStore() };
}

describe("Login view", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    authMocks.login.mockResolvedValue({
      access_token: "access",
      refresh_token: "refresh",
      token_type: "bearer",
    });
  });

  it("signs in a user and routes to the forced password step when required", async () => {
    authMocks.me.mockResolvedValue({
      user_id: "user-id",
      phone_country_code: "+86",
      phone_number: "13800138000",
      role: "user",
      status: "active",
      credit_balance: 8420,
      must_change_password: true,
    });
    const { wrapper, router } = await mountLogin();

    await wrapper.get("[data-testid='phone-number']").setValue("13800138000");
    await wrapper.get("[data-testid='password']").setValue("safe-password");
    await wrapper.get("[data-testid='login-submit']").trigger("submit");
    await flushPromises();

    expect(authMocks.login).toHaveBeenCalledWith("13800138000", "safe-password");
    expect(router.currentRoute.value.name).toBe("password-change");
  });

  it("does not let a normal user enter the administrator shell", async () => {
    authMocks.me.mockResolvedValue({
      user_id: "user-id",
      phone_country_code: "+86",
      phone_number: "13800138000",
      role: "user",
      status: "active",
      credit_balance: 8420,
      must_change_password: false,
    });
    const { wrapper, session } = await mountLogin("admin");

    await wrapper.get("[data-testid='phone-number']").setValue("13800138000");
    await wrapper.get("[data-testid='password']").setValue("safe-password");
    await wrapper.get("[data-testid='login-submit']").trigger("submit");
    await flushPromises();

    expect(wrapper.text()).toContain("此账号没有管理员权限");
    expect(session.isAuthenticated).toBe(false);
  });
});
