import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createMemoryHistory, createRouter } from "vue-router";

import { useSessionStore } from "@/store/session";

import RegisterView from "./register.vue";

const authMocks = vi.hoisted(() => ({
  register: vi.fn(),
  me: vi.fn(),
}));

vi.mock("@/modules/auth/api", () => ({
  authApi: authMocks,
}));

async function mountRegister() {
  const pinia = createPinia();
  setActivePinia(pinia);
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/register", component: RegisterView },
      { path: "/", name: "home", component: { template: "<div />" } },
      { path: "/:pathMatch(.*)*", component: { template: "<div />" } },
    ],
  });
  await router.push("/register");
  await router.isReady();
  const wrapper = mount(RegisterView, {
    global: { plugins: [pinia, router] },
  });
  return { wrapper, session: useSessionStore() };
}

describe("Register view", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("validates the form inline before creating an invited account", async () => {
    authMocks.register.mockResolvedValue({
      access_token: "access",
      refresh_token: "refresh",
      token_type: "bearer",
    });
    authMocks.me.mockResolvedValue({
      user_id: "user-id",
      phone_country_code: "+86",
      phone_number: "13800138000",
      role: "user",
      status: "active",
      credit_balance: 1000,
      must_change_password: false,
    });
    const { wrapper } = await mountRegister();

    await wrapper.get("[data-testid='register-submit']").trigger("submit");
    expect(wrapper.text()).toContain("请输入有效的中国大陆手机号");
    expect(authMocks.register).not.toHaveBeenCalled();

    await wrapper.get("[data-testid='phone-number']").setValue("13800138000");
    await wrapper.get("[data-testid='invite-code']").setValue("INV-CODE");
    await wrapper.get("[data-testid='password']").setValue("safe-password-123");
    await wrapper.get("[data-testid='accepted-terms']").setValue(true);
    await wrapper.get("[data-testid='register-submit']").trigger("submit");
    await flushPromises();

    expect(authMocks.register).toHaveBeenCalledWith(
      "13800138000",
      "safe-password-123",
      "INV-CODE",
    );
  });

  it("clears a partially issued Session when identity bootstrap fails", async () => {
    authMocks.register.mockResolvedValue({
      access_token: "access",
      refresh_token: "refresh",
      token_type: "bearer",
    });
    authMocks.me.mockRejectedValue(new Error("无法读取账号"));
    const { wrapper, session } = await mountRegister();

    await wrapper.get("[data-testid='phone-number']").setValue("13800138000");
    await wrapper.get("[data-testid='invite-code']").setValue("INV-CODE");
    await wrapper.get("[data-testid='password']").setValue("safe-password-123");
    await wrapper.get("[data-testid='accepted-terms']").setValue(true);
    await wrapper.get("[data-testid='register-submit']").trigger("submit");
    await flushPromises();

    expect(wrapper.text()).toContain("无法读取账号");
    expect(session.isAuthenticated).toBe(false);
    expect(sessionStorage.getItem("office-ai.refresh-token")).toBeNull();
  });
});
