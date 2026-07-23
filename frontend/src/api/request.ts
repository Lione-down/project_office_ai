import { getApiBaseUrl } from "@/utils/runtime-config";

export interface ApiClientOptions {
  baseUrl: string;
  fetchImpl?: typeof fetch;
}

export interface ApiRequestOptions {
  accessToken?: string;
  headers?: HeadersInit;
}

interface ErrorEnvelope {
  error?: {
    error_code?: string;
    message?: string;
    trace_id?: string;
  };
}

async function readErrorEnvelope(response: Response): Promise<ErrorEnvelope> {
  try {
    return (await response.json()) as ErrorEnvelope;
  } catch {
    return {};
  }
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
    const headers = new Headers(options.headers);
    new Headers(init.headers).forEach((value, key) => headers.set(key, value));
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
    if (response.status === 204) {
      return undefined as T;
    }
    if (!response.ok) {
      const payload = await readErrorEnvelope(response);
      throw new ApiError(
        payload.error?.error_code ?? "request_failed",
        payload.error?.message ?? "请求失败",
        payload.error?.trace_id ?? response.headers.get("X-Trace-ID"),
        response.status,
      );
    }
    return (await response.json()) as T;
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
    delete(path: string, options?: ApiRequestOptions): Promise<void> {
      return request<void>(path, { method: "DELETE" }, options);
    },
    postForm<T>(
      path: string,
      body: FormData,
      headers: HeadersInit,
      options?: ApiRequestOptions,
    ): Promise<T> {
      return request<T>(
        path,
        {
          method: "POST",
          headers,
          body,
        },
        options,
      );
    },
    async download(path: string, options: ApiRequestOptions = {}): Promise<Blob> {
      const headers = new Headers(options.headers);
      if (options.accessToken) {
        headers.set("Authorization", `Bearer ${options.accessToken}`);
      }
      const response = await fetchImpl(
        `${normalizedBaseUrl}/${path.replace(/^\//, "")}`,
        { method: "GET", headers },
      );
      if (!response.ok) {
        const payload = await readErrorEnvelope(response);
        throw new ApiError(
          payload.error?.error_code ?? "request_failed",
          payload.error?.message ?? "请求失败",
          payload.error?.trace_id ?? response.headers.get("X-Trace-ID"),
          response.status,
        );
      }
      return response.blob();
    },
  };
}

export const apiClient = createApiClient({
  baseUrl: getApiBaseUrl(),
});
