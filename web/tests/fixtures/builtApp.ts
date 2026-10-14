import type { Page } from "@playwright/test";
import { readFile } from "node:fs/promises";
import { basename, extname } from "node:path";
import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";

// Run the real bundle with explicit local API fixtures, without opening a server.
export async function builtApp(page: Page, image?: Buffer) {
  await page.route("**/*", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (
      path === "/api/short-formats" ||
      path.startsWith("/api/short-formats/") ||
      path === "/api/scene-preview"
    ) {
      const formats = JSON.parse(
        await readFile(
          new URL("../../../backend/mycut/short_formats.json", import.meta.url),
          "utf8",
        ),
      );
      if (path === "/api/short-formats")
        return route.fulfill({
          json: {
            formats: formats.map((format: { id: string }) => ({
              ...format,
              preview_url: `/api/short-formats/${format.id}/preview.png`,
            })),
            fonts: {
              sans: "Sans",
              serif: "Serifada",
              mono: "Monoespaçada",
              condensed: "Condensada",
            },
          },
        });
      const selected = formats.find((item: { id: string }) =>
        path.includes(`/${item.id}/`),
      );
      const input =
        path === "/api/scene-preview"
          ? route.request().postDataJSON()
          : {
              scene: {
                title: "Da ideia à ação",
                layout: "flow",
                items: [
                  "Você define a tarefa",
                  "O agente executa",
                  "Você revisa o resultado",
                ],
                narration: "",
              },
              accent: selected.accent,
              visual_style: { format_id: selected.id },
            };
      if (input.scene.image_id && image)
        input._test_image = image.toString("base64");
      const python =
        process.env.MYCUT_TEST_PYTHON ||
        [
          "../../../.venv-studio/bin/python",
          "../../../.venv-narration/bin/python",
        ]
          .map((path) => fileURLToPath(new URL(path, import.meta.url)))
          .find(existsSync) ||
        "python3";
      return route.fulfill({
        contentType: "image/png",
        body: execFileSync(
          python,
          [fileURLToPath(new URL("render_preview.py", import.meta.url))],
          { input: JSON.stringify(input) },
        ),
      });
    }
    if (path === "/api/health")
      return route.fulfill({
        json: { status: "ok", worker_online: true, ffmpeg: true },
      });
    if (
      path === "/" ||
      /^\/assets\/[^/]+$/.test(path) ||
      path === "/mark.svg"
    ) {
      const file =
        path === "/"
          ? "index.html"
          : path === "/mark.svg"
            ? "mark.svg"
            : `assets/${basename(path)}`;
      const mime: Record<string, string> = {
        ".html": "text/html",
        ".js": "text/javascript",
        ".css": "text/css",
        ".svg": "image/svg+xml",
        ".woff2": "font/woff2",
      };
      return route.fulfill({
        body: await readFile(new URL(`../../dist/${file}`, import.meta.url)),
        contentType: mime[extname(file)],
      });
    }
    return route.abort();
  });
}
