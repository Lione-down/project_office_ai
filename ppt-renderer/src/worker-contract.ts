import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, relative, resolve, sep } from "node:path";

import {
  PresentationContractError,
  parsePresentationPlan,
  presentationPlanSha256,
} from "./contracts.js";
import { renderPresentation } from "./renderer.js";

export const RENDER_REQUEST_SCHEMA_VERSION = "ppt-renderer.request.v1";
export const RENDER_RESPONSE_SCHEMA_VERSION = "ppt-renderer.response.v1";
const REQUEST_ID =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const inFlightRequests = new Map<string, Promise<RenderSuccess>>();

interface RenderRequest {
  schema_version: typeof RENDER_REQUEST_SCHEMA_VERSION;
  request_id: string;
  plan: unknown;
}

interface RenderSuccess {
  schema_version: typeof RENDER_RESPONSE_SCHEMA_VERSION;
  request_id: string;
  status: "succeeded";
  output_key: string;
  sha256: string;
  byte_size: number;
  slide_count: number;
  template_code: string;
  template_version: string;
  renderer_version: string;
  plan_sha256: string;
}

interface RenderFailure {
  schema_version: typeof RENDER_RESPONSE_SCHEMA_VERSION;
  request_id: string | null;
  status: "failed";
  error: {
    code: string;
    message: string;
    retryable: boolean;
  };
}

export type RenderResponse = RenderSuccess | RenderFailure;

export async function executeRenderRequest(
  input: unknown,
  workRoot: string,
): Promise<RenderResponse> {
  let requestId: string | null = null;
  try {
    const request = parseRequest(input);
    requestId = request.request_id;
    const requestKey = `${resolve(workRoot)}:${request.request_id}`;
    const active = inFlightRequests.get(requestKey);
    if (active) return await active;

    const operation = renderValidatedRequest(request, workRoot);
    inFlightRequests.set(requestKey, operation);
    try {
      return await operation;
    } finally {
      if (inFlightRequests.get(requestKey) === operation) {
        inFlightRequests.delete(requestKey);
      }
    }
  } catch (error) {
    if (error instanceof PresentationContractError) {
      return failure(requestId, error.code, "PresentationPlan 无效", false);
    }
    if (error instanceof WorkerContractError) {
      return failure(requestId, error.code, error.message, error.retryable);
    }
    return failure(
      requestId,
      "render_internal_error",
      "Renderer 内部错误",
      true,
    );
  }
}

async function renderValidatedRequest(
  request: RenderRequest,
  workRoot: string,
): Promise<RenderSuccess> {
  const plan = parsePresentationPlan(request.plan);
  const planSha256 = presentationPlanSha256(plan);
  const outputKey = `requests/${request.request_id}/presentation.pptx`;
  const outputPath = resolveInside(workRoot, outputKey);
  const sidecarPath = resolveInside(
    workRoot,
    `requests/${request.request_id}/result.json`,
  );
  await mkdir(dirname(outputPath), { recursive: true });

  const existing = await readExisting(
    sidecarPath,
    outputPath,
    request.request_id,
    outputKey,
    planSha256,
    plan,
  );
  if (existing) return existing;

  const result = await renderPresentation(plan, outputPath);
  const response: RenderSuccess = {
    schema_version: RENDER_RESPONSE_SCHEMA_VERSION,
    request_id: request.request_id,
    status: "succeeded",
    output_key: outputKey,
    sha256: result.sha256,
    byte_size: result.byteSize,
    slide_count: result.slideCount,
    template_code: result.templateCode,
    template_version: result.templateVersion,
    renderer_version: result.rendererVersion,
    plan_sha256: planSha256,
  };
  await writeFile(sidecarPath, JSON.stringify(response), { flag: "w" });
  return response;
}

function parseRequest(input: unknown): RenderRequest {
  if (
    typeof input !== "object" ||
    input === null ||
    Array.isArray(input) ||
    Object.keys(input).sort().join(",") !== "plan,request_id,schema_version"
  ) {
    throw new WorkerContractError(
      "render_request_invalid",
      "Renderer 请求无效",
      false,
    );
  }
  const candidate = input as Record<string, unknown>;
  if (
    candidate.schema_version !== RENDER_REQUEST_SCHEMA_VERSION ||
    typeof candidate.request_id !== "string" ||
    !REQUEST_ID.test(candidate.request_id)
  ) {
    throw new WorkerContractError(
      "render_request_invalid",
      "Renderer 请求无效",
      false,
    );
  }
  return candidate as unknown as RenderRequest;
}

function resolveInside(root: string, key: string): string {
  const resolvedRoot = resolve(root);
  const target = resolve(resolvedRoot, ...key.split("/"));
  const relativePath = relative(resolvedRoot, target);
  if (
    !relativePath ||
    relativePath.startsWith(`..${sep}`) ||
    relativePath === ".."
  ) {
    throw new WorkerContractError(
      "render_output_key_invalid",
      "Renderer 输出定位无效",
      false,
    );
  }
  return target;
}

async function readExisting(
  sidecarPath: string,
  outputPath: string,
  requestId: string,
  outputKey: string,
  planSha256: string,
  plan: ReturnType<typeof parsePresentationPlan>,
): Promise<RenderSuccess | null> {
  let sidecar: string;
  try {
    sidecar = await readFile(sidecarPath, "utf8");
  } catch (error) {
    const code = (error as NodeJS.ErrnoException).code;
    if (code === "ENOENT") return null;
    throw error;
  }
  let response: RenderSuccess;
  try {
    response = JSON.parse(sidecar) as RenderSuccess;
  } catch (error) {
    throw new WorkerContractError(
      "render_replay_corrupt",
      "Renderer replay checkpoint 无效",
      false,
    );
  }
  if (response.plan_sha256 !== planSha256) {
    throw new WorkerContractError(
      "render_request_conflict",
      "Renderer request_id 已用于不同输入",
      false,
    );
  }
  if (
    response.schema_version !== RENDER_RESPONSE_SCHEMA_VERSION ||
    response.request_id !== requestId ||
    response.status !== "succeeded" ||
    response.output_key !== outputKey ||
    response.slide_count !== plan.slides.length ||
    response.template_code !== plan.template.code ||
    response.template_version !== plan.template.version ||
    response.renderer_version !== plan.renderer_version ||
    !/^[a-f0-9]{64}$/.test(response.sha256) ||
    !Number.isSafeInteger(response.byte_size) ||
    response.byte_size <= 0
  ) {
    throw new WorkerContractError(
      "render_replay_corrupt",
      "Renderer replay checkpoint 无效",
      false,
    );
  }
  let bytes: Buffer;
  try {
    bytes = await readFile(outputPath);
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return null;
    throw error;
  }
  const digest = createHash("sha256").update(bytes).digest("hex");
  if (digest !== response.sha256 || bytes.length !== response.byte_size) {
    return null;
  }
  return response;
}

function failure(
  requestId: string | null,
  code: string,
  message: string,
  retryable: boolean,
): RenderFailure {
  return {
    schema_version: RENDER_RESPONSE_SCHEMA_VERSION,
    request_id: requestId,
    status: "failed",
    error: { code, message, retryable },
  };
}

class WorkerContractError extends Error {
  constructor(
    readonly code: string,
    message: string,
    readonly retryable: boolean,
  ) {
    super(message);
  }
}
