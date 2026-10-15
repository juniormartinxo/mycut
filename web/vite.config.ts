import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const dataDir = process.env.MYCUT_DATA_DIR || resolve(import.meta.dirname, "../.data");
let apiPort = Number(process.env.MYCUT_PORT || 8321);
if (!process.env.MYCUT_PORT) {
  try {
    apiPort = JSON.parse(readFileSync(resolve(dataDir, "http.json"), "utf8")).port;
  } catch {
    // Before the first launch, use the default API port.
  }
}
if (!Number.isInteger(apiPort) || apiPort < 1024 || apiPort > 65535) {
  throw new Error("Porta da API inválida. Inicie o MyCut para atualizar .data/http.json.");
}
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: { "/api": "http://127.0.0.1:" + apiPort },
  },
});
