import { apiClient } from "@/api/request";

import type {
  AdminModelSummary,
  AdminAssetSummary,
  AdminUserSummary,
  AdminOverview,
  AuditLogSummary,
  CredentialSummary,
  InviteCreate,
  InviteSummary,
  ProviderSummary,
  SensitivePayload,
} from "./types";

interface AdminApiClient {
  get<T>(path: string, options?: { accessToken?: string }): Promise<T>;
  post<T>(
    path: string,
    body: unknown,
    options?: { accessToken?: string },
  ): Promise<T>;
  deleteJson?(
    path: string,
    body: unknown,
    options?: { accessToken?: string },
  ): Promise<void>;
  postDownload?(
    path: string,
    body: unknown,
    options?: { accessToken?: string },
  ): Promise<Blob>;
}

export function createAdminApi(client: AdminApiClient) {
  const listInvites = (accessToken: string) =>
    client.get<InviteSummary[]>("/admin/invite-codes", { accessToken });
  const listProviders = (accessToken: string) =>
    client.get<ProviderSummary[]>("/admin/providers", { accessToken });
  const listCredentials = (accessToken: string) =>
    client.get<CredentialSummary[]>("/admin/credentials", { accessToken });
  const listModels = (accessToken: string) =>
    client.get<AdminModelSummary[]>("/admin/models", { accessToken });
  const listUsers = (accessToken: string) =>
    client.get<AdminUserSummary[]>("/admin/users", { accessToken });
  const listAssets = (accessToken: string) =>
    client.get<AdminAssetSummary[]>("/admin/assets", { accessToken });
  const listAuditLogs = (accessToken: string) =>
    client.get<AuditLogSummary[]>("/admin/audit-logs", { accessToken });

  return {
    listInvites,
    listProviders,
    listCredentials,
    listModels,
    listUsers,
    listAssets,
    listAuditLogs,
    listCredits: listAuditLogs,
    createInvite(payload: InviteCreate, accessToken: string) {
      return client.post<InviteSummary>("/admin/invite-codes", payload, {
        accessToken,
      });
    },
    revealCredential(
      credentialId: string,
      payload: SensitivePayload,
      accessToken: string,
    ) {
      return client.post<{ credential_id: string; api_key: string }>(
        `/admin/credentials/${credentialId}/reveal`,
        payload,
        { accessToken },
      );
    },
    changeUserStatus(
      userId: string,
      status: string,
      payload: SensitivePayload,
      accessToken: string,
    ) {
      return client.post<void>(
        `/admin/users/${userId}/status`,
        { ...payload, status },
        { accessToken },
      );
    },
    resetPassword(
      userId: string,
      payload: SensitivePayload & { new_password: string },
      accessToken: string,
    ) {
      return client.post<void>(
        `/admin/users/${userId}/reset-password`,
        payload,
        { accessToken },
      );
    },
    adjustCredits(
      userId: string,
      amount: number,
      payload: SensitivePayload,
      accessToken: string,
    ) {
      return client.post(
        "/admin/credits/adjustments",
        { ...payload, user_id: userId, amount },
        {
          accessToken,
          headers: { "Idempotency-Key": crypto.randomUUID() },
        } as never,
      );
    },
    openAsset(
      assetId: string,
      action: "preview" | "download",
      payload: SensitivePayload,
      accessToken: string,
    ) {
      if (!client.postDownload) throw new Error("下载客户端不可用");
      return client.postDownload(`/admin/assets/${assetId}/${action}`, payload, {
        accessToken,
      });
    },
    deleteAsset(
      assetId: string,
      payload: SensitivePayload,
      accessToken: string,
    ) {
      if (!client.deleteJson) throw new Error("删除客户端不可用");
      return client.deleteJson(`/admin/assets/${assetId}`, payload, { accessToken });
    },
    async getOverview(accessToken: string): Promise<AdminOverview> {
      const [providers, credentials, models, invites] = await Promise.all([
        listProviders(accessToken),
        listCredentials(accessToken),
        listModels(accessToken),
        listInvites(accessToken),
      ]);
      return {
        providerCount: providers.length,
        credentialCount: credentials.length,
        modelCount: models.length,
        inviteCount: invites.length,
      };
    },
  };
}

export const adminApi = createAdminApi(apiClient);
