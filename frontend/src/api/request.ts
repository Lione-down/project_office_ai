import { getApiBaseUrl } from "@/utils/runtime-config";

export interface ApiClientOptions {
  baseUrl: string;
  fetchImpl?: typeof fetch;
}

export interface ApiRequestOptions {
  accessToken?: string;
}

interface ErrorEnvelope {
  error?: {
    error_code?: string;
    message?: string;
    trace_id?: string;
  };
}

export class ApiError extends Error {
  constructor(
    public readonly code: string,
    message: string,
    public readonly traceId: string | null,
    public readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export function createApiClient({ baseUrl, fetchImpl = fetch }: ApiClientOptions) {
  const normalizedBaseUrl = baseUrl.replace(/\/$/, "");

  async function request<T>(
    path: string,
    init: RequestInit,
    options: ApiRequestOptions = {},
  ): Promise<T> {
    const headers = new Headers(init.headers);
    headers.set("Accept", "application/json");
    if (options.accessToken) {
      headers.set("Authorization", `Bearer ${options.accessToken}`);
    }
    const response = await fetchImpl(
      `${normalizedBaseUrl}/${path.replace(/^\//, "")}`,
      {
        ...init,
        headers,
      },
    );
    const payload = (await response.json()) as T & ErrorEnvelope;
    if (!response.ok) {
      throw new ApiError(
        payload.error?.error_code ?? "request_failed",
        payload.error?.message ?? "请求失败",
        payload.error?.trace_id ?? response.headers.get("X-Trace-ID"),
        response.status,
      );
    }
    return payload;
  }

  return {
    get<T>(path: string, options?: ApiRequestOptions): Promise<T> {
      return request<T>(path, { method: "GET" }, options);
    },
    post<T>(
      path: string,
      body: unknown,
      options?: ApiRequestOptions,
    ): Promise<T> {
      return request<T>(
        path,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
        options,
      );
    },
    patch<T>(
      path: string,
      body: unknown,
      options?: ApiRequestOptions,
    ): Promise<T> {
      return request<T>(
        path,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
        options,
      );
    },
  };
}

export const apiClient = createApiClient({
  baseUrl: getApiBaseUrl(),
});
