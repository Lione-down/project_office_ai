import { describe, expect, it } from "vitest";

import {
  compatibleTemplateOptions,
  safeTemplatePreviewUrl,
} from "./template-catalog";


describe("template catalog presentation contract", () => {
  it("accepts only versioned local SVG preview assets", () => {
    expect(
      safeTemplatePreviewUrl(
        "/template-previews/ppt.executive-blue.v1/cover.svg",
      ),
    ).toBe("/template-previews/ppt.executive-blue.v1/cover.svg");
    expect(safeTemplatePreviewUrl("https://example.com/preview.png")).toBe("");
    expect(safeTemplatePreviewUrl("data:image/svg+xml;base64,unsafe")).toBe("");
    expect(safeTemplatePreviewUrl("/template-previews/../private.svg")).toBe("");
    expect(safeTemplatePreviewUrl("C:\\private\\preview.svg")).toBe("");
  });

  it("shows only templates compatible with the selected Skill", () => {
    const templates = [
      {
        template_code: "ppt.operating-review.v1",
        compatible_skills: ["ppt.sales-business-review.v1"],
      },
      {
        template_code: "ppt.executive-blue.v1",
        compatible_skills: [
          "ppt.sales-business-review.v1",
          "ppt.knowledge-education.v1",
        ],
      },
    ];

    expect(
      compatibleTemplateOptions(
        templates,
        "ppt.knowledge-education.v1",
      ).map((template) => template.template_code),
    ).toEqual(["ppt.executive-blue.v1"]);
  });
});
