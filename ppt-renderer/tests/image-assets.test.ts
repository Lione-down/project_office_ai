import { createHash } from "node:crypto";

import { describe, expect, it } from "vitest";

import { PresentationContractError, parsePresentationPlan } from "../src/contracts.js";
import { ONE_PIXEL_PNG, samplePlan } from "./fixtures/sample-plan.js";


const bytes = Buffer.from(ONE_PIXEL_PNG.split(",", 2)[1], "base64");

function imagePlan() {
  return {
    ...structuredClone(samplePlan),
    images: {
      "hero-image": {
        asset_id: "019fad40-0000-7000-8000-000000000001",
        asset_version: 1,
        data_uri: ONE_PIXEL_PNG,
        mime_type: "image/png",
        byte_size: bytes.length,
        sha256: createHash("sha256").update(bytes).digest("hex"),
        width: 1,
        height: 1,
        crop_mode: "cover",
        alt_text: "脱敏合成图片",
      },
    },
  };
}

describe("immutable image assets", () => {
  it("accepts integrity-bound image metadata and explicit crop mode", () => {
    const parsed = parsePresentationPlan(imagePlan());
    expect(parsed.images["hero-image"].crop_mode).toBe("cover");
  });

  it.each([
    ["sha256", "0".repeat(64)],
    ["width", 2],
    ["byte_size", bytes.length + 1],
    ["crop_mode", "stretch"],
  ])("fails closed when %s does not match decoded bytes", (field, value) => {
    const plan = imagePlan();
    plan.images["hero-image"] = {
      ...plan.images["hero-image"],
      [field]: value,
    };
    expect(() => parsePresentationPlan(plan)).toThrow(PresentationContractError);
  });
});
