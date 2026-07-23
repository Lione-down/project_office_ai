import { apiClient } from "@/api/request";

import type {
  AdminModelSummary,
  AdminOverview,
  CredentialSummary,
  InviteCreate,
  InviteSummary,
  ProviderSummary,
} from "./types";

interface AdminApiClient {
  get<T>(path: string, options?: { accessToken?: string }): Promise<T>;
  post<T>(
    path: string,
    body: unknown,
    options?: { accessToken?: string },
  ): Promise<T>;
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

  return {
    listInvites,
    listProviders,
    listCredentials,
    listModels,
    createInvite(payload: InviteCreate, accessToken: string) {
      return client.post<InviteSummary>("/admin/invite-codes", payload, {
        accessToken,
      });
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
