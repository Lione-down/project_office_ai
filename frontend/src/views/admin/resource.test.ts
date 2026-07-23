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
  listUsers: vi.fn(),
  listAssets: vi.fn(),
  listCredits: vi.fn(),
  listAuditLogs: vi.fn(),
  revealCredential: vi.fn(),
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
    adminMocks.listUsers.mockResolvedValue([]);
    adminMocks.listAssets.mockResolvedValue([]);
    adminMocks.listCredits.mockResolvedValue([]);
    adminMocks.listAuditLogs.mockResolvedValue([]);
    adminMocks.revealCredential.mockResolvedValue({
      credential_id: "credential-id",
      api_key: "one-time-secret",
    });
  });

  it("keeps Credential masked until the unified sensitive dialog succeeds", async () => {
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
    await wrapper.get("[data-testid='credential-reveal']").trigger("click");
    expect(wrapper.get("[role='dialog']").text()).toContain("重新认证");
    expect(wrapper.get("[role='dialog']").text()).toContain("操作原因");
    expect(wrapper.text()).not.toContain("one-time-secret");
    await wrapper.get("input[autocomplete='current-password']").setValue("admin-password");
    await wrapper.get("textarea").setValue("凭据轮换核查");
    await wrapper.get("[data-testid='sensitive-confirm']").trigger("click");
    await flushPromises();
    expect(adminMocks.revealCredential).toHaveBeenCalledTimes(1);
    expect(wrapper.text()).toContain("one-time-secret");
    expect(wrapper.find("[role='dialog']").exists()).toBe(false);
  });

  it("loads the five audited admin pages from real API methods", async () => {
    adminMocks.listUsers.mockResolvedValue([
      {
        user_id: "user-id",
        masked_phone: "+86 138****8001",
        status: "active",
        credit_balance: 100,
        must_change_password: false,
      },
    ]);
    const wrapper = await mountResource("users");

    expect(adminMocks.listUsers).toHaveBeenCalledWith("access");
    expect(wrapper.text()).toContain("+86 138****8001");
    expect(wrapper.findAll("tbody tr")).toHaveLength(1);
    expect(wrapper.get("[data-testid='user-status-action']").text()).toContain("停用");
  });

  it("cancels without sending a sensitive request and disables duplicate submit", async () => {
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
    await wrapper.get("[data-testid='credential-reveal']").trigger("click");
    await wrapper.get("[data-testid='sensitive-cancel']").trigger("click");
    expect(adminMocks.revealCredential).not.toHaveBeenCalled();
    expect(wrapper.find("[role='dialog']").exists()).toBe(false);
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
