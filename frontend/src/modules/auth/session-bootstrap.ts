import { useSessionStore } from "@/store/session";

import { authApi } from "./api";

type SessionStore = ReturnType<typeof useSessionStore>;

export async function bootstrapSession(session: SessionStore) {
  if (session.hasBootstrapped) return session.isAuthenticated;
  if (session.isAuthenticated) {
    session.markBootstrapped();
    return true;
  }

  const refreshToken = session.restoreRefreshToken();
  if (!refreshToken) {
    session.markBootstrapped();
    return false;
  }

  try {
    const tokens = await authApi.refresh(refreshToken);
    session.setTokens(tokens);
    session.applyCurrentUser(await authApi.me(tokens.access_token));
    return true;
  } catch {
    session.clearSession();
    return false;
  } finally {
    session.markBootstrapped();
  }
}
