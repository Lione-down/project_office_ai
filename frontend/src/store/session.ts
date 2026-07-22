import { defineStore } from "pinia";
import { ref } from "vue";

import type { UserRole } from "@/types/access";

export const useSessionStore = defineStore("session", () => {
  const isAuthenticated = ref(false);
  const role = ref<UserRole | null>(null);
  return { isAuthenticated, role };
});
