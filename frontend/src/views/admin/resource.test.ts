import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useSessionStore } from "@/store/session";

import AdminResourceView from "./resource.vue";

const adminMocks = vi.hoisted(() => ({
  listInvites: vi.fn(),
  listProviders: vi.fn(),
  listCredentials: vi.fn(),
  listModels: vi.fn(),
}));

vi.mock("@/modules/admin/api", () => ({
  adminApi: adminMocks,
}));

async function mountResource(
  section:
    | "invites"
    | "providers"
    | "credentials"
    | "models"
    | "users"
    | "tasks"
    | "assets"
    | "credits"
    | "audit-logs",
) {
  const pinia = createPinia();
  setActivePinia(pinia);
  useSessionStore().setTokens({
    access_token: "access",
    refresh_token: "refresh",
    token_type: "bearer",
  });
  const wrapper = mount(AdminResourceView, {
    props: { section },
    global: { plugins: [pinia] },
  });
  await flushPromises();
  return wrapper;
}

describe("Admin resource view", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    adminMocks.listInvites.mockResolvedValue([]);
    adminMocks.listProviders.mockResolvedValue([]);
    adminMocks.listCredentials.mockResolvedValue([]);
    adminMocks.listModels.mockResolvedValue([]);
  });

  it("keeps Credential values masked and Reveal unavailable in T4-001", async () => {
    adminMocks.listCredentials.mockResolvedValue([
      {
        credential_id: "credential-id",
        provider_id: "provider-id",
        name: "agnes-prod",
        masked_key: "sk-••••9K2A",
        status: "active",
        rpm_limit: 120,
        tpm_limit: 240000,
        max_concurrency: 8,
        rotation_source: "initial",
        last_test_status: "passed",
      },
    ]);
    const wrapper = await mountResource("credentials");

    expect(wrapper.text()).toContain("sk-••••9K2A");
    expect(wrapper.text()).toContain("Reveal 与重新认证闭环将在 T4-002 接入");
    expect(wrapper.find("[data-testid='credential-reveal']").exists()).toBe(false);
  });

  it("shows a truthful disabled boundary for admin APIs reserved for T4-002", async () => {
    const wrapper = await mountResource("users");

    expect(wrapper.text()).toContain("用户管理");
    expect(wrapper.text()).toContain("当前页面仅提供功能壳");
    expect(wrapper.text()).toContain("T4-002");
    expect(wrapper.findAll("tbody tr")).toHaveLength(0);
  });

  it("shows masked invite summaries without inventing the one-time code", async () => {
    adminMocks.listInvites.mockResolvedValue([
      {
        invite_id: "invite-id",
        code_prefix: "INV-7K3P",
        max_uses: 50,
        used_count: 12,
        expires_at: "2026-08-31T00:00:00Z",
        status: "active",
        registration_credit: 1000,
      },
    ]);
    const wrapper = await mountResource("invites");

    expect(wrapper.text()).toContain("INV-7K3P••••");
    expect(wrapper.text()).not.toContain("INV-ONE-TIME");
  });
});
