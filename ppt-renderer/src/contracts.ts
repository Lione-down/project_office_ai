import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";

import type { ErrorObject, ValidateFunction } from "ajv";
import Ajv2020 from "ajv/dist/2020.js";

export const PRESENTATION_PLAN_SCHEMA_ID = "presentation-plan.v1";
export const RENDERER_VERSION = "ppt-renderer.v1";

const schema = JSON.parse(
  readFileSync(
    new URL("./presentation-plan.v1.schema.json", import.meta.url),
    "utf8",
  ),
) as object;
const Ajv2020Constructor = Ajv2020 as unknown as new (
  options: Record<string, unknown>,
) => {
  compile<T>(input: object): ValidateFunction<T>;
};
const ajv = new Ajv2020Constructor({
  allErrors: true,
  strict: true,
  strictNumbers: true,
  validateFormats: false,
});
const validateSchema = ajv.compile<PresentationPlan>(schema);

export interface PresentationTemplateRef {
  code:
    | "ppt.executive-blue.v1"
    | "ppt.operating-review.v1"
    | "ppt.data-story.v1";
  version: "1.0.0";
}

export interface PresentationMetadata {
  title: string;
  subject: string;
  author: string;
  company: string;
  revision: string;
}

export interface ImageData {
  data_uri: string;
  alt_text: string;
}

export interface ChartDataSource {
  kind: "chart";
  categories: string[];
  series: Array<{ name: string; values: number[] }>;
}

export interface TableDataSource {
  kind: "table";
  columns: string[];
  rows: Array<Array<string | number>>;
}

interface Geometry {
  x: number;
  y: number;
  w: number;
  h: number;
}

interface EvidenceElement {
  evidence_ids: string[];
}

export interface TextElement extends Geometry, EvidenceElement {
  type: "text";
  text: string;
}

export interface ImageElement extends Geometry {
  type: "image";
  image_id: string;
  decorative?: true;
  evidence_ids?: string[];
}

export interface TableElement extends Geometry, EvidenceElement {
  type: "table";
  data_source_id: string;
}

export interface ChartElement extends Geometry, EvidenceElement {
  type: "chart";
  chart_type: "bar" | "line" | "pie";
  data_source_id: string;
}

export interface SourceElement extends Geometry, EvidenceElement {
  type: "source";
  text: string;
}

export type PresentationElement =
  | TextElement
  | ImageElement
  | TableElement
  | ChartElement
  | SourceElement;

export interface PresentationSlide {
  layout: "title" | "content" | "section" | "closing";
  title: string;
  subtitle?: string;
  speaker_notes: string[];
  elements: PresentationElement[];
}

export interface PresentationPlan {
  schema_version: typeof PRESENTATION_PLAN_SCHEMA_ID;
  renderer_version: typeof RENDERER_VERSION;
  template: PresentationTemplateRef;
  locale: "zh-CN";
  metadata: PresentationMetadata;
  evidence_ids: string[];
  images: Record<string, ImageData>;
  data_sources: Record<string, ChartDataSource | TableDataSource>;
  slides: PresentationSlide[];
}

export class PresentationContractError extends Error {
  constructor(
    readonly code: string,
    readonly validationErrors: ErrorObject[] = [],
  ) {
    super(code);
    this.name = "PresentationContractError";
  }
}

export function parsePresentationPlan(input: unknown): PresentationPlan {
  if (!validateSchema(input)) {
    const isEvidenceError = (validateSchema.errors ?? []).some(
      (error) =>
        error.params &&
        "missingProperty" in error.params &&
        error.params.missingProperty === "evidence_ids",
    );
    throw new PresentationContractError(
      isEvidenceError
        ? "presentation_evidence_invalid"
        : "presentation_plan_invalid",
      validateSchema.errors ?? [],
    );
  }
  const plan = input as PresentationPlan;
  validateReferences(plan);
  return structuredClone(plan);
}

export function presentationPlanSha256(plan: PresentationPlan): string {
  return createHash("sha256").update(canonicalJson(plan)).digest("hex");
}

function canonicalJson(value: unknown): string {
  if (typeof value === "number") {
    const fixed = value.toFixed(6).replace(/(?:\.0+|(\.\d+?)0+)$/, "$1");
    return fixed === "-0" ? "0" : fixed;
  }
  if (value === null || typeof value !== "object") {
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) {
    return `[${value.map((item) => canonicalJson(item)).join(",")}]`;
  }
  const record = value as Record<string, unknown>;
  return `{${Object.keys(record)
    .sort()
    .map(
      (key) => `${JSON.stringify(key)}:${canonicalJson(record[key])}`,
    )
    .join(",")}}`;
}

function validateReferences(plan: PresentationPlan): void {
  const evidence = new Set(plan.evidence_ids);
  for (const slide of plan.slides) {
    for (const element of slide.elements) {
      for (const value of [element.x, element.y, element.w, element.h]) {
        validatePlanNumber(value);
      }
      if ("evidence_ids" in element) {
        if (
          !element.evidence_ids ||
          element.evidence_ids.some((evidenceId) => !evidence.has(evidenceId))
        ) {
          throw new PresentationContractError("presentation_evidence_invalid");
        }
      }
      if (element.type === "image" && !(element.image_id in plan.images)) {
        throw new PresentationContractError(
          "presentation_data_reference_invalid",
        );
      }
      if (element.type === "table" || element.type === "chart") {
        const source = plan.data_sources[element.data_source_id];
        if (!source || source.kind !== element.type) {
          throw new PresentationContractError(
            "presentation_data_reference_invalid",
          );
        }
        if (
          source.kind === "chart" &&
          source.series.some(
            (series) => series.values.length !== source.categories.length,
          )
        ) {
          throw new PresentationContractError(
            "presentation_data_reference_invalid",
          );
        }
        if (source.kind === "chart") {
          for (const series of source.series) {
            series.values.forEach(validatePlanNumber);
          }
        }
        if (
          source.kind === "table" &&
          source.rows.some((row) => row.length !== source.columns.length)
        ) {
          throw new PresentationContractError(
            "presentation_data_reference_invalid",
          );
        }
        if (source.kind === "table") {
          for (const row of source.rows) {
            for (const value of row) {
              if (typeof value === "number") validatePlanNumber(value);
            }
          }
        }
      }
    }
  }
}

function validatePlanNumber(value: number): void {
  const scaled = value * 1_000_000;
  if (
    !Number.isFinite(value) ||
    Math.abs(value) > 1_000_000_000_000 ||
    Math.abs(scaled - Math.round(scaled)) > 0.0001
  ) {
    throw new PresentationContractError("presentation_plan_invalid");
  }
}
