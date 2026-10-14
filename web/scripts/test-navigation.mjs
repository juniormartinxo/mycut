import { build } from "vite";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const root = fileURLToPath(new URL("../", import.meta.url));
const outDir = await mkdtemp(join(tmpdir(), "mycut-navigation-"));
try {
  await build({
    root,
    configFile: false,
    logLevel: "error",
    ssr: { noExternal: true },
    build: {
      ssr: "unit/navigation.test.tsx",
      outDir,
      rollupOptions: { output: { entryFileNames: "navigation.mjs" } },
    },
  });
  const result = spawnSync(process.execPath, [join(outDir, "navigation.mjs")], {
    stdio: "inherit",
  });
  process.exitCode = result.status ?? 1;
} finally {
  await rm(outDir, { recursive: true, force: true });
}
