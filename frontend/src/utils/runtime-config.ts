export function getApiBaseUrl(): string {
  return import.meta.env.VITE_API_BASE_URL ?? "/api/v1";
}

export function getAppEnvironmentLabel(): string {
  return import.meta.env.VITE_APP_ENV_LABEL?.trim() || "本地环境";
}
