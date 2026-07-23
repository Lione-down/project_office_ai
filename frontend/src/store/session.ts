import { defineStore } from "pinia";
import { ref } from "vue";

import type { UserRole } from "@/types/access";

export const useSessionStore = defineStore("session", () => {
  const isAuthenticated = ref(false);
  const role = ref<UserRole | null>(null);
  const accessToken = ref<string | null>(null);

  function setAccessToken(token: string) {
    accessToken.value = token;
    isAuthenticated.value = true;
  }

  function clearSession() {
    accessToken.value = null;
    isAuthenticated.value = false;
    role.value = null;
  }

  return { isAuthenticated, role, accessToken, setAccessToken, clearSession };
});
