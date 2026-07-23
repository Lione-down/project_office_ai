import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useSessionStore } from "@/store/session";

import AdminOverviewView from "./overview.vue";

const adminMocks = vi.hoisted(() => ({
  getOverview: vi.fn(),
}));

vi.mock("@/modules/admin/api", () => ({
  adminApi: adminMocks,
}));

describe("Admin overview", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("summarizes real delivered registry counts and names the sensitive boundary", async () => {
    adminMocks.getOverview.mockResolvedValue({
      providerCount: 2,
      credentialCount: 3,
      modelCount: 2,
      inviteCount: 36,
    });
    const pinia = createPinia();
    setActivePinia(pinia);
    useSessionStore().setTokens({
      access_token: "access",
      refresh_token: "refresh",
      token_type: "bearer",
    });
    const wrapper = mount(AdminOverviewView, {
      global: {
        plugins: [pinia],
        stubs: { RouterLink: { template: "<a><slot /></a>" } },
      },
    });
    await flushPromises();

    expect(wrapper.text()).toContain("已配置 Provider");
    expect(wrapper.text()).toContain("2");
    expect(wrapper.text()).toContain("敏感操作需要重新认证");
  });
});
