import { createHash } from "node:crypto";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

import JSZip from "jszip";
import { afterEach, describe, expect, it } from "vitest";

import { renderPresentation } from "../src/renderer.js";
import { SYSTEM_TEMPLATES } from "../src/templates.js";
import { clonePlan } from "./fixtures/sample-plan.js";

const temporaryRoots: string[] = [];

afterEach(async () => {
  await Promise.all(
    temporaryRoots.splice(0).map((root) => rm(root, { recursive: true })),
  );
});

async function outputPath(name: string): Promise<string> {
  const root = await mkdtemp(join(tmpdir(), "office-ai-ppt-"));
  temporaryRoots.push(root);
  return join(root, name);
}

async function structuralDigest(filePath: string): Promise<string> {
  const archive = await JSZip.loadAsync(await readFile(filePath));
  const chartIds = Object.keys(archive.files)
    .map((name) => /^ppt\/charts\/chart(\d+)\.xml$/.exec(name)?.[1])
    .filter((value): value is string => value !== undefined)
    .sort((left, right) => Number(left) - Number(right));
  const canonicalChartId = new Map(
    chartIds.map((value, index) => [value, String(index + 1)]),
  );
  const members: Array<[string, string]> = [];
  for (const name of Object.keys(archive.files).sort()) {
    if (
      name.endsWith("/") ||
      name === "docProps/core.xml" ||
      name.startsWith("ppt/media/") ||
      name.startsWith("ppt/embeddings/")
    ) {
      continue;
    }
    const body = await archive.file(name)?.async("string");
    const normalizeChartIds = (value: string): string =>
      value
        .replaceAll(/chart(\d+)\.xml/g, (_match, id: string) => {
          return `chart${canonicalChartId.get(id) ?? id}.xml`;
        })
        .replaceAll(
          /Microsoft_Excel_Worksheet(\d+)\.xlsx/g,
          (_match, id: string) => {
            return `Microsoft_Excel_Worksheet${canonicalChartId.get(id) ?? id}.xlsx`;
          },
        );
    members.push([
      normalizeChartIds(name),
      normalizeChartIds((body ?? "").replaceAll(/\s+/g, " ")),
    ]);
  }
  members.sort(([left], [right]) => left.localeCompare(right));
  return createHash("sha256").update(JSON.stringify(members)).digest("hex");
}

describe("deterministic PPTX rendering", () => {
  it("renders all required OOXML structures and metadata", async () => {
    const target =
      process.env.OFFICE_AI_PPT_SAMPLE_OUTPUT ??
      (await outputPath("sample.pptx"));
    const result = await renderPresentation(clonePlan(), target);
    const archive = await JSZip.loadAsync(await readFile(target));
    const names = Object.keys(archive.files);
    const core = await archive.file("docProps/core.xml")?.async("string");
    const slides = names.filter((name) => /^ppt\/slides\/slide\d+\.xml$/.test(name));
    const layouts = names.filter((name) =>
      /^ppt\/slideLayouts\/slideLayout\d+\.xml$/.test(name),
    );
    const layoutXml = (
      await Promise.all(
        layouts.map((name) => archive.file(name)?.async("string") ?? ""),
      )
    ).join("\n");
    const masterXml = (
      await Promise.all(
        names
          .filter((name) => /^ppt\/slideMasters\/slideMaster\d+\.xml$/.test(name))
          .map((name) => archive.file(name)?.async("string") ?? ""),
      )
    ).join("\n");
    const slideXml = (
      await Promise.all(
        slides.map((name) => archive.file(name)?.async("string") ?? ""),
      )
    ).join("\n");

    expect(result.slideCount).toBe(4);
    expect(result.byteSize).toBeGreaterThan(1_000);
    expect(result.sha256).toMatch(/^[a-f0-9]{64}$/);
    expect(slides).toHaveLength(4);
    expect(layouts.length).toBeGreaterThanOrEqual(4);
    expect(names.some((name) => name.startsWith("ppt/slideMasters/"))).toBe(true);
    expect(names.some((name) => name.startsWith("ppt/notesSlides/"))).toBe(true);
    expect(names.some((name) => name.startsWith("ppt/charts/"))).toBe(true);
    expect(names.some((name) => name.startsWith("ppt/media/"))).toBe(true);
    expect(core).toContain("2026 上半年销售经营汇报");
    expect(core).toContain("Office AI");
    expect(layoutXml).toContain("<p:ph");
    expect(masterXml).toContain("<a:fld");
    expect(slideXml).toContain("<a:tbl>");
    expect(slideXml).not.toContain("Evidence:");
    expect(slideXml).toContain("来源：脱敏 synthetic sales dataset");
    const notesXml = (
      await Promise.all(
        names
          .filter((name) => /^ppt\/notesSlides\/notesSlide\d+\.xml$/.test(name))
          .map((name) => archive.file(name)?.async("string") ?? ""),
      )
    ).join("\n");
    expect(notesXml).toContain("Evidence:");
    expect(notesXml).toContain("ev-revenue");
  });

  it("produces structurally equivalent OOXML for identical inputs", async () => {
    const first = await outputPath("first.pptx");
    const second = await outputPath("second.pptx");

    await renderPresentation(clonePlan(), first);
    await renderPresentation(clonePlan(), second);

    expect(await structuralDigest(first)).toBe(await structuralDigest(second));
  });

  it.each(SYSTEM_TEMPLATES)(
    "renders certified template $code@$version",
    async (template) => {
      const plan = clonePlan();
      plan.template = { code: template.code, version: template.version };
      const target = await outputPath(`${template.code}.pptx`);

      const result = await renderPresentation(plan, target);

      expect(result.templateCode).toBe(template.code);
      expect(result.templateVersion).toBe("1.0.0");
    },
  );
});
