import { test, expect, type Page } from "@playwright/test";
import { builtApp } from "./fixtures/builtApp";
import type { Project } from "../src/types";

const id = "fedcba0987654321fedcba0987654321";
// Local, synthetic PNG; never an external image or provider request.
const png = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADUlEQVQIHWP4z8AAAAMBAQDJ/pLvAAAAAElFTkSuQmCC",
  "base64",
);
// A complete script in Markdown, with a table and a code block, longer than the formats' 12 000 characters.
const prompt = [
  "# Short: Da Ideia ao Filme com IA",
  "",
  "| Tempo | Narração (off) | Texto na tela |",
  "| --- | --- | --- |",
  '| 0–3 s | "Seus vídeos de IA mudam de rosto a cada cena?" | O PROBLEMA NÃO É A IA |',
  '| 50–58 s | "Resultado: isso." | PROMPT NO COMENTÁRIO FIXADO |',
  "",
  "```",
  "Studio character reference sheet, 85mm lens --ar 3:2",
  "```",
  "",
  "Corredor cilíndrico de painéis de alumínio escovado. ".repeat(260),
].join("\n");

function freeProject(brief: string): Project {
  return {
    id,
    title: "Short livre",
    brief,
    free: true,
    warnings: ["Afirmação não verificada: O Runway custa US$ 12 por mês."],
    description: "",
    tags: "",
    sources: "",
    accent: "#F2B544",
    accent_locked: false,
    visual_style: null,
    images: [],
    revision: 2,
    created_at: 0,
    updated_at: 0,
    jobs: [],
    audio_matches_script: false,
    usage_total: {
      input: 0,
      cache_read: 0,
      cache_write: 0,
      output: 0,
      reasoning: 0,
      web_searches: 0,
      credits: 0,
      usd: 0,
      unpriced: 0,
    },
    scenes: [
      {
        id: "0123456789abcdef0123456789abcdef",
        title: "O PROBLEMA NÃO É A IA",
        narration: "Seus vídeos de IA mudam de rosto a cada cena?",
        layout: "statement",
        items: [],
        blocks: [
          { id: "1123456789abcdef0123456789abcdef", width: 100, height: 100, align: "center", object: null },
        ],
      },
    ],
  } as Project;
}
async function agents(page: Page) {
  await page.route("**/api/integrations", (route) =>
    route.fulfill({
      json: {
        agents: Object.fromEntries(
          ["research", "writer", "director", "reviewer"].map((role) => [
            role,
            { provider: "codex", model: "" },
          ]),
        ),
        runner: { online: true, protocol: 3, providers: { codex: true } },
        elevenlabs: { connected: true, voice_id: "junior123" },
      },
    }),
  );
}

test("Livre aceita o prompt inteiro com anexos e abre o projeto sem formato", async ({
  page,
}, info) => {
  await builtApp(page);
  await agents(page);
  let sent: { body: string; type: string } | null = null;
  let saved: Project | null = null;
  await page.route("**/api/projects/free", (route) => {
    const request = route.request();
    sent = {
      body: request.postDataBuffer()!.toString("utf8"),
      type: request.headers()["content-type"],
    };
    const project = JSON.parse(
      sent.body.split('name="project"')[1].split("\r\n\r\n")[1].split("\r\n--")[0],
    );
    saved = freeProject(project.brief);
    return route.fulfill({ status: 201, json: saved });
  });
  await page.route("**/api/projects", (route) =>
    route.fulfill({ json: saved ? [saved] : [] }),
  );
  await page.route(`**/api/projects/${id}`, (route) =>
    route.fulfill({ json: saved }),
  );
  await page.goto("/#/novo");
  await page.getByRole("radio", { name: "Livre", exact: true }).check();
  await expect(page.getByLabel("Cor de fundo", { exact: true })).toHaveCount(0);
  await expect(page.getByLabel("Abrir editor vazio")).toHaveCount(0);
  const field = page.getByLabel("Prompt do Short livre");
  await field.fill(prompt);
  await expect(field).toHaveValue(prompt);
  await page.locator(".free-attachments input[type=file]").setInputFiles([
    { name: "ira.png", mimeType: "image/png", buffer: png },
    { name: "corredor.png", mimeType: "image/png", buffer: png },
    { name: "fichas.md", mimeType: "text/markdown", buffer: Buffer.from("Ira Vale: 38 anos, 172 cm.") },
  ]);
  await expect(page.getByRole("list", { name: "Imagens anexadas" }).getByRole("listitem")).toHaveText(["ira.png", "corredor.png"]);
  await page.getByRole("button", { name: "Remover corredor.png" }).click();
  await expect(field).toHaveValue(`${prompt}\n\n## Anexo: fichas.md\n\nIra Vale: 38 anos, 172 cm.`);
  await expect
    .poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth))
    .toBe(true);
  await page.screenshot({ path: info.outputPath("free-new.png"), fullPage: true });
  await page.getByRole("button", { name: "Produzir com agentes" }).click();
  await expect(page.getByRole("heading", { name: "O ponto de partida dos agentes" })).toBeVisible();
  expect(sent!.type).toContain("multipart/form-data");
  expect(sent!.body).toContain('filename="ira.png"');
  expect(sent!.body).not.toContain('filename="corredor.png"');
  expect(saved!.brief.startsWith(prompt)).toBe(true);
  expect(saved!.brief.length).toBeGreaterThan(12000);
  await expect(page.getByLabel("Prompt do Short livre")).toHaveValue(saved!.brief);
  await expect(page.getByRole("radio", { name: "Radar tech" })).toHaveCount(0);
  await expect(page.getByText("Afirmação não verificada: O Runway custa US$ 12 por mês.")).toBeVisible();
  await page.screenshot({ path: info.outputPath("free-brief.png"), fullPage: true });
});
