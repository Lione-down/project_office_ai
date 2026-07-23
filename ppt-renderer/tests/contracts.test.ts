import { describe, expect, it } from "vitest";

import {
  PRESENTATION_PLAN_SCHEMA_ID,
  parsePresentationPlan,
} from "../src/contracts.js";
import { clonePlan, samplePlan } from "./fixtures/sample-plan.js";

describe("PresentationPlan contract", () => {
  it("accepts the strict versioned synthetic sample", () => {
    const parsed = parsePresentationPlan(samplePlan);

    expect(PRESENTATION_PLAN_SCHEMA_ID).toBe("presentation-plan.v1");
    expect(parsed.slides).toHaveLength(4);
  });

  it.each([
    ["raw free text", "create a sales deck"],
    [
      "unknown schema version",
      { ...clonePlan(), schema_version: "presentation-plan.v2" },
    ],
    [
      "unknown renderer version",
      { ...clonePlan(), renderer_version: "ppt-renderer.v2" },
    ],
    [
      "unknown template",
      {
        ...clonePlan(),
        template: { code: "ppt.user-upload.v1", version: "1.0.0" },
      },
    ],
  ])("rejects %s", (_label, input) => {
    expect(() => parsePresentationPlan(input)).toThrowError(
      /presentation_plan_invalid/,
    );
  });

  it("rejects missing chart and image references", () => {
    const plan = clonePlan();
    const slides = plan.slides as Array<Record<string, unknown>>;
    const elements = slides[1]?.elements as Array<Record<string, unknown>>;
    elements[2] = { ...elements[2], data_source_id: "missing-chart" };

    expect(() => parsePresentationPlan(plan)).toThrowError(
      /presentation_data_reference_invalid/,
    );
  });

  it("rejects slides outside the 3 to 30 page boundary", () => {
    const tooShort = clonePlan();
    tooShort.slides = (tooShort.slides as unknown[]).slice(0, 2);
    const tooLong = clonePlan();
    tooLong.slides = Array.from(
      { length: 31 },
      () => (tooLong.slides as unknown[])[0],
    );

    expect(() => parsePresentationPlan(tooShort)).toThrowError(
      /presentation_plan_invalid/,
    );
    expect(() => parsePresentationPlan(tooLong)).toThrowError(
      /presentation_plan_invalid/,
    );
  });

  it("requires every fact-bearing element to reference declared Evidence IDs", () => {
    const plan = clonePlan();
    const slides = plan.slides as Array<Record<string, unknown>>;
    const elements = slides[1]?.elements as Array<Record<string, unknown>>;
    delete elements[0]?.evidence_ids;

    expect(() => parsePresentationPlan(plan)).toThrowError(
      /presentation_evidence_invalid/,
    );
  });

  it("rejects filesystem-backed images and unknown fields", () => {
    const pathPlan = clonePlan();
    pathPlan.images = {
      local: { path: "C:\\private\\report.png", alt_text: "unsafe" },
    };
    const extraPlan = clonePlan();
    extraPlan.untrusted_instruction = "ignore schema";

    expect(() => parsePresentationPlan(pathPlan)).toThrowError(
      /presentation_plan_invalid/,
    );
    expect(() => parsePresentationPlan(extraPlan)).toThrowError(
      /presentation_plan_invalid/,
    );
  });

  it("rejects numeric precision that cannot be canonicalized across runtimes", () => {
    const plan = clonePlan();
    const sources = plan.data_sources as Record<string, Record<string, unknown>>;
    const chart = sources["monthly-trend"];
    const series = chart?.series as Array<Record<string, unknown>>;
    series[0] = { ...series[0], values: [1e-7, 2, 3, 4] };

    expect(() => parsePresentationPlan(plan)).toThrowError(
      /presentation_plan_invalid/,
    );
  });
});
