import { createHash } from "node:crypto";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

import JSZip from "jszip";
import { afterEach, describe, expect, it } from "vitest";

import { renderPresentation } from "../src/renderer.js";
import { ONE_PIXEL_PNG, clonePlan } from "./fixtures/sample-plan.js";

const temporaryRoots: string[] = [];
const posterBytes = Buffer.from(ONE_PIXEL_PNG.split(",", 2)[1]!, "base64");

afterEach(async () => {
  await Promise.all(
    temporaryRoots.splice(0).map((root) => rm(root, { recursive: true })),
  );
});

describe("video compatibility fallback", () => {
  it("renders only a poster image relationship and never an external video URL", async () => {
    const plan = clonePlan();
    plan.images["video-poster"] = {
      asset_id: "019fad70-0000-7000-8000-000000000001",
      asset_version: 1,
      data_uri: ONE_PIXEL_PNG,
      mime_type: "image/png",
      byte_size: posterBytes.length,
      sha256: createHash("sha256").update(posterBytes).digest("hex"),
      width: 1,
      height: 1,
      crop_mode: "contain",
      alt_text: "视频预览图；MP4 作为独立附件交付",
    };
    plan.slides[1]!.elements.push({
      type: "image",
      image_id: "video-poster",
      decorative: true,
      x: 8.65,
      y: 1.35,
      w: 3.75,
      h: 4.85,
    });
    const root = await mkdtemp(join(tmpdir(), "office-ai-video-fallback-"));
    temporaryRoots.push(root);
    const target = join(root, "fallback.pptx");

    await renderPresentation(plan, target);

    const archive = await JSZip.loadAsync(await readFile(target));
    const names = Object.keys(archive.files);
    const relationships = (
      await Promise.all(
        names
          .filter((name) => name.endsWith(".rels"))
          .map((name) => archive.file(name)?.async("string") ?? ""),
      )
    ).join("\n");
    const slides = (
      await Promise.all(
        names
          .filter((name) => /^ppt\/slides\/slide\d+\.xml$/.test(name))
          .map((name) => archive.file(name)?.async("string") ?? ""),
      )
    ).join("\n");

    expect(names.some((name) => name.startsWith("ppt/media/image"))).toBe(true);
    expect(names.some((name) => /\.(mp4|mov|avi)$/i.test(name))).toBe(false);
    expect(
      names.some(
        (name) =>
          name.startsWith("ppt/embeddings/") &&
          /\.(mp4|mov|avi)$/i.test(name),
      ),
    ).toBe(false);
    expect(relationships).not.toContain("TargetMode=\"External\"");
    expect(relationships).not.toMatch(/video|media\/.*\.mp4/i);
    expect(slides).not.toContain("<p:video");
  });
});
