import type { UserRole } from "@/types/access";

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface CurrentUser {
  user_id: string;
  phone_country_code: string;
  phone_number: string;
  role: UserRole;
  status: string;
  credit_balance: number;
  must_change_password: boolean;
}

export interface SessionAccessSnapshot {
  isAuthenticated: boolean;
  role: UserRole | null;
  mustChangePassword: boolean;
}
