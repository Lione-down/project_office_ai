import { apiClient } from "@/api/request";

import type { AuthTokens, CurrentUser } from "./types";

interface AuthApiClient {
  get<T>(path: string, options?: { accessToken?: string }): Promise<T>;
  post<T>(
    path: string,
    body: unknown,
    options?: { accessToken?: string },
  ): Promise<T>;
}

export function createAuthApi(client: AuthApiClient) {
  return {
    login(phoneNumber: string, password: string) {
      return client.post<AuthTokens>("/auth/login", {
        phone_number: phoneNumber,
        password,
      });
    },
    register(phoneNumber: string, password: string, inviteCode: string) {
      return client.post<AuthTokens>("/auth/register", {
        phone_number: phoneNumber,
        password,
        invite_code: inviteCode,
        accepted_terms: true,
      });
    },
    refresh(refreshToken: string) {
      return client.post<AuthTokens>("/auth/refresh", {
        refresh_token: refreshToken,
      });
    },
    logout(accessToken: string) {
      return client.post<void>("/auth/logout", undefined, { accessToken });
    },
    me(accessToken: string) {
      return client.get<CurrentUser>("/auth/me", { accessToken });
    },
    changePassword(
      currentPassword: string,
      newPassword: string,
      accessToken: string,
    ) {
      return client.post<AuthTokens>(
        "/auth/change-password",
        {
          current_password: currentPassword,
          new_password: newPassword,
        },
        { accessToken },
      );
    },
  };
}

export const authApi = createAuthApi(apiClient);
