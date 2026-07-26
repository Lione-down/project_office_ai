import { execFileSync } from "node:child_process";
import { copyFile, mkdir } from "node:fs/promises";
import { join, resolve } from "node:path";

const outputRoot = resolve(
  process.env.PPT_RENDERER_BUILD_OUT_DIR ?? "dist",
);
const tscEntry = resolve("node_modules/typescript/bin/tsc");

execFileSync(
  process.execPath,
  [tscEntry, "-p", "tsconfig.build.json", "--outDir", outputRoot],
  { stdio: "inherit" },
);
await mkdir(outputRoot, { recursive: true });
await copyFile(
  new URL("../src/presentation-plan.v1.schema.json", import.meta.url),
  join(outputRoot, "presentation-plan.v1.schema.json"),
);
