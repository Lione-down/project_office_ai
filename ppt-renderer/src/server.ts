import {
  createServer,
  type IncomingMessage,
  type Server,
  type ServerResponse,
} from "node:http";
import { pathToFileURL } from "node:url";

import { executeRenderRequest } from "./worker-contract.js";

const DEFAULT_MAX_BODY_BYTES = 10 * 1024 * 1024;

export function createRendererServer(options?: {
  workRoot?: string;
  maxBodyBytes?: number;
}): Server {
  const workRoot = options?.workRoot ?? process.env.WORK_ROOT ?? "/app/work";
  const maxBodyBytes =
    options?.maxBodyBytes ??
    parsePositiveInteger(
      process.env.MAX_REQUEST_BYTES,
      DEFAULT_MAX_BODY_BYTES,
    );
  return createServer(async (request, response) => {
    if (request.method === "GET" && request.url === "/health") {
      sendJson(response, 200, { status: "ok" });
      return;
    }
    if (request.method !== "POST" || request.url !== "/v1/render") {
      sendJson(response, 404, {
        status: "failed",
        error: { code: "not_found", message: "资源不存在", retryable: false },
      });
      return;
    }
    try {
      requireJson(request);
      const body = await readBoundedJson(request, maxBodyBytes);
      const result = await executeRenderRequest(body, workRoot);
      sendJson(response, result.status === "succeeded" ? 200 : 422, result);
    } catch (error) {
      const isBodyError = error instanceof RequestBodyError;
      sendJson(response, isBodyError ? error.status : 500, {
        schema_version: "ppt-renderer.response.v1",
        request_id: null,
        status: "failed",
        error: {
          code: isBodyError ? error.code : "render_internal_error",
          message: isBodyError ? error.message : "Renderer 内部错误",
          retryable: false,
        },
      });
    }
  });
}

const entrypoint = process.argv[1];
if (
  entrypoint !== undefined &&
  import.meta.url === pathToFileURL(entrypoint).href
) {
  const port = parsePositiveInteger(process.env.PORT, 3000);
  createRendererServer().listen(port, "0.0.0.0");
}

function requireJson(request: IncomingMessage): void {
  const contentType = request.headers["content-type"]?.split(";")[0]?.trim();
  if (contentType !== "application/json") {
    throw new RequestBodyError(
      "render_content_type_invalid",
      "Renderer 只接受 JSON",
      415,
    );
  }
}

async function readBoundedJson(
  request: IncomingMessage,
  limit: number,
): Promise<unknown> {
  const declared = Number(request.headers["content-length"]);
  if (
    !Number.isSafeInteger(declared) ||
    declared < 2 ||
    declared > limit ||
    request.headers["transfer-encoding"] !== undefined
  ) {
    throw new RequestBodyError(
      "render_body_invalid",
      "Renderer 请求体无效",
      413,
    );
  }
  const chunks: Buffer[] = [];
  let received = 0;
  for await (const chunk of request) {
    const buffer = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
    received += buffer.length;
    if (received > limit || received > declared) {
      throw new RequestBodyError(
        "render_body_too_large",
        "Renderer 请求体超过上限",
        413,
      );
    }
    chunks.push(buffer);
  }
  if (received !== declared) {
    throw new RequestBodyError(
      "render_body_invalid",
      "Renderer 请求体无效",
      400,
    );
  }
  try {
    return JSON.parse(Buffer.concat(chunks).toString("utf8"));
  } catch {
    throw new RequestBodyError(
      "render_json_invalid",
      "Renderer JSON 无效",
      400,
    );
  }
}

function sendJson(
  response: ServerResponse,
  statusCode: number,
  body: unknown,
): void {
  const payload = Buffer.from(JSON.stringify(body));
  response.writeHead(statusCode, {
    "Content-Type": "application/json; charset=utf-8",
    "Content-Length": payload.length,
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
  });
  response.end(payload);
}

function parsePositiveInteger(
  value: string | undefined,
  fallback: number,
): number {
  if (value === undefined) return fallback;
  const parsed = Number(value);
  if (!Number.isSafeInteger(parsed) || parsed <= 0) {
    throw new Error("renderer numeric environment is invalid");
  }
  return parsed;
}

class RequestBodyError extends Error {
  constructor(
    readonly code: string,
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}
