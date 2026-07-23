import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createMemoryHistory, createRouter } from "vue-router";

import { useSessionStore } from "@/store/session";

import ChangePasswordView from "./change-password.vue";

const authMocks = vi.hoisted(() => ({
  changePassword: vi.fn(),
  logout: vi.fn(),
  me: vi.fn(),
}));

vi.mock("@/modules/auth/api", () => ({
  authApi: authMocks,
}));

async function mountChangePassword() {
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
    role: "user",
    status: "active",
    credit_balance: 8420,
    must_change_password: true,
  });
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/password/change", component: ChangePasswordView },
      { path: "/", name: "home", component: { template: "<div />" } },
      { path: "/login", name: "login", component: { template: "<div />" } },
      { path: "/:pathMatch(.*)*", component: { template: "<div />" } },
    ],
  });
  await router.push("/password/change");
  await router.isReady();
  const wrapper = mount(ChangePasswordView, {
    global: { plugins: [pinia, router] },
  });
  return { wrapper, router, session };
}

describe("Change password view", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("replaces the Session tokens and clears the forced-change gate", async () => {
    authMocks.changePassword.mockResolvedValue({
      access_token: "next-access",
      refresh_token: "next-refresh",
      token_type: "bearer",
    });
    authMocks.me.mockResolvedValue({
      user_id: "user-id",
      phone_country_code: "+86",
      phone_number: "13800138000",
      role: "user",
      status: "active",
      credit_balance: 8420,
      must_change_password: false,
    });
    const { wrapper, router, session } = await mountChangePassword();

    await wrapper.get("[data-testid='current-password']").setValue("old-password");
    await wrapper.get("[data-testid='new-password']").setValue("new-password-123");
    await wrapper.get("[data-testid='confirm-password']").setValue("new-password-123");
    await wrapper.get("[data-testid='change-password-submit']").trigger("submit");
    await flushPromises();

    expect(session.accessToken).toBe("next-access");
    expect(session.mustChangePassword).toBe(false);
    expect(router.currentRoute.value.name).toBe("home");
  });

  it("revokes the forced-password Session when the user exits", async () => {
    authMocks.logout.mockResolvedValue(undefined);
    const { wrapper, router, session } = await mountChangePassword();

    await wrapper.get("[data-testid='logout-forced-password']").trigger("click");
    await flushPromises();

    expect(authMocks.logout).toHaveBeenCalledWith("access");
    expect(session.isAuthenticated).toBe(false);
    expect(sessionStorage.getItem("office-ai.refresh-token")).toBeNull();
    expect(router.currentRoute.value.name).toBe("login");
  });
});
