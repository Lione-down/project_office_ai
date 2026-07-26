import { createHash } from "node:crypto";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";

import JSZip from "jszip";
import { afterAll, describe, expect, it } from "vitest";

import {
  parsePresentationPlan,
  type PresentationPlan,
} from "../../src/contracts.js";
import { renderPresentation } from "../../src/renderer.js";

const repoRoot = path.resolve(import.meta.dirname, "../../..");
const manifestPath = path.join(
  repoRoot,
  "golden-data/manifests/sales-pilot-v1.json",
);
const planPath = path.join(
  repoRoot,
  "golden-data/manifests/sales-pilot-v1.presentation-plan.json",
);
const outputRoot = await mkdtemp(path.join(tmpdir(), "office-ai-golden-ppt-"));

afterAll(async () => {
  await rm(outputRoot, { recursive: true, force: true });
});

async function loadJson(filePath: string): Promise<unknown> {
  return JSON.parse(await readFile(filePath, "utf8")) as unknown;
}

async function structuralDigest(bytes: Buffer): Promise<string> {
  const archive = await JSZip.loadAsync(bytes);
  const members: Array<[string, string]> = [];
  for (const name of Object.keys(archive.files).sort()) {
    if (name.endsWith("/") || name === "docProps/core.xml") {
      continue;
    }
    const payload = await archive.file(name)?.async("uint8array");
    members.push([
      name,
      createHash("sha256").update(payload ?? new Uint8Array()).digest("hex"),
    ]);
  }
  return createHash("sha256").update(JSON.stringify(members)).digest("hex");
}

describe("sales-pilot-v1 presentation golden regression", () => {
  it("renders the authorized pilot 20 times with deterministic structure", async () => {
    const manifest = (await loadJson(manifestPath)) as {
      coverage: { label: string };
      repetitions: { presentation: number };
      expected_presentation: {
        path: string;
        sha256: string;
        byte_size: number;
        slide_count: number;
      };
    };
    const plan = parsePresentationPlan(
      await loadJson(planPath),
    ) as PresentationPlan;
    const expectedBytes = await readFile(
      path.join(repoRoot, manifest.expected_presentation.path),
    );
    const expectedHash = createHash("sha256")
      .update(expectedBytes)
      .digest("hex");
    const expectedStructure = await structuralDigest(expectedBytes);
    const structures: string[] = [];

    expect(manifest.coverage.label).toBe("1/10 pilot");
    expect(manifest.repetitions.presentation).toBe(20);
    expect(expectedHash).toBe(manifest.expected_presentation.sha256);
    expect(expectedBytes.byteLength).toBe(
      manifest.expected_presentation.byte_size,
    );
    for (let index = 0; index < manifest.repetitions.presentation; index += 1) {
      const target = path.join(outputRoot, `run-${index + 1}.pptx`);
      const result = await renderPresentation(plan, target);
      const bytes = await readFile(target);
      structures.push(await structuralDigest(bytes));
      expect(result.slideCount).toBe(
        manifest.expected_presentation.slide_count,
      );
      expect(bytes.byteLength).toBe(
        manifest.expected_presentation.byte_size,
      );
    }

    expect(new Set(structures)).toEqual(new Set([expectedStructure]));
  });

  it("contains no macro, external relationship, PII, or embedded payload", async () => {
    const manifest = (await loadJson(manifestPath)) as {
      expected_presentation: { path: string };
    };
    const presentation = await readFile(
      path.join(repoRoot, manifest.expected_presentation.path),
    );
    const archive = await JSZip.loadAsync(presentation);
    const names = Object.keys(archive.files);
    const xmlParts = await Promise.all(
      names
        .filter((name) => name.endsWith(".xml") || name.endsWith(".rels"))
        .map(async (name) => archive.file(name)?.async("string") ?? ""),
    );
    const text = xmlParts.join("\n");

    expect(names.some((name) => /vbaProject\.bin$/i.test(name))).toBe(false);
    expect(
      names.some(
        (name) =>
          name.startsWith("ppt/embeddings/") && !name.endsWith("/"),
      ),
    ).toBe(false);
    expect(/TargetMode="External"/i.test(text)).toBe(false);
    expect(/1[3-9]\d{9}/.test(text)).toBe(false);
    expect(/0\d{2,3}[- ]?\d{7,8}/.test(text)).toBe(false);
    expect(/[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}/.test(text)).toBe(false);
    const creator = /<dc:creator>([^<]*)<\/dc:creator>/i.exec(text)?.[1] ?? "";
    expect(["", "Office AI"]).toContain(creator.trim());
  });
});
