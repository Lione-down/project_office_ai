import type { UserRole } from "@/types/access";

export interface SessionAccessSnapshot {
  isAuthenticated: boolean;
  role: UserRole | null;
}
