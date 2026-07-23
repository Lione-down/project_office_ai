import { defineStore } from "pinia";
import { ref } from "vue";

import type { AuthTokens, CurrentUser } from "@/modules/auth/types";
import type { UserRole } from "@/types/access";

const REFRESH_TOKEN_STORAGE_KEY = "office-ai.refresh-token";

function readStoredRefreshToken() {
  try {
    return globalThis.sessionStorage?.getItem(REFRESH_TOKEN_STORAGE_KEY) ?? null;
  } catch {
    return null;
  }
}

function storeRefreshToken(token: string | null) {
  try {
    if (token) {
      globalThis.sessionStorage?.setItem(REFRESH_TOKEN_STORAGE_KEY, token);
    } else {
      globalThis.sessionStorage?.removeItem(REFRESH_TOKEN_STORAGE_KEY);
    }
  } catch {
    // A blocked storage API must not prevent an in-memory Session.
  }
}

export const useSessionStore = defineStore("session", () => {
  const isAuthenticated = ref(false);
  const role = ref<UserRole | null>(null);
  const accessToken = ref<string | null>(null);
  const refreshToken = ref<string | null>(null);
  const userId = ref<string | null>(null);
  const phoneNumber = ref<string | null>(null);
  const creditBalance = ref(0);
  const mustChangePassword = ref(false);
  const hasBootstrapped = ref(false);

  function setAccessToken(token: string) {
    accessToken.value = token;
    isAuthenticated.value = true;
  }

  function setTokens(tokens: AuthTokens) {
    accessToken.value = tokens.access_token;
    refreshToken.value = tokens.refresh_token;
    isAuthenticated.value = true;
    storeRefreshToken(tokens.refresh_token);
  }

  function applyCurrentUser(user: CurrentUser) {
    userId.value = user.user_id;
    phoneNumber.value = user.phone_number;
    role.value = user.role;
    creditBalance.value = user.credit_balance;
    mustChangePassword.value = user.must_change_password;
  }

  function clearSession() {
    accessToken.value = null;
    refreshToken.value = null;
    isAuthenticated.value = false;
    role.value = null;
    userId.value = null;
    phoneNumber.value = null;
    creditBalance.value = 0;
    mustChangePassword.value = false;
    storeRefreshToken(null);
  }

  function restoreRefreshToken() {
    const token = readStoredRefreshToken();
    refreshToken.value = token;
    return token;
  }

  function markBootstrapped() {
    hasBootstrapped.value = true;
  }

  return {
    isAuthenticated,
    role,
    accessToken,
    refreshToken,
    userId,
    phoneNumber,
    creditBalance,
    mustChangePassword,
    hasBootstrapped,
    setAccessToken,
    setTokens,
    applyCurrentUser,
    clearSession,
    restoreRefreshToken,
    markBootstrapped,
  };
});
