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
  const livre = page.getByRole("radio", { name: "Livre", exact: true });
  await livre.check();
  await expect(page.getByLabel("Prompt do Short livre")).toBeVisible();
  // Choosing a format leaves Livre, and Livre can be chosen again.
  await page.getByRole("radio", { name: "Radar tech", exact: true }).check();
  await expect(livre).not.toBeChecked();
  await expect(page.getByLabel("Pauta ou link")).toBeVisible();
  await expect(page.getByLabel("Cor de fundo", { exact: true })).toHaveValue("#121c24");
  await livre.check();
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

test("Short livre mostra o estilo gerado, a pausa do roteiro e o pacote de publicação", async ({ page }, info) => {
  await builtApp(page);
  await agents(page);
  const project: Project = {
    ...freeProject(prompt),
    title: "Por que seu vídeo de IA muda o rosto do personagem",
    description: "O erro número 1 em vídeo com IA é pular a pré-produção.",
    visual_style: {
      format_id: "free", channel_name: "MYCUT", font: "sans", google_font: "Roboto", background: "#0b2a33",
      text_color: "#e6f1f2", media_mode: "mixed", image_source: "library", loop: true,
      captions: { words: 3, position: "middle", font_size: 72, keywords: ["ficha", "cenário"] },
    },
    publication: {
      titles: ["Por que seu vídeo de IA muda o rosto do personagem", "Da ideia ao filme com IA em 4 etapas"],
      description: "O erro número 1 em vídeo com IA é pular a pré-produção.",
      hashtags: ["#Shorts", "#IA", "#FilmeComIA"],
      pinned_comment: "Prompt-mestre: você é um diretor de cinema.\nJunto de cada prompt em inglês, traga a tradução em português.",
    },
  };
  project.scenes = [{ ...project.scenes[0], narration: "Resultado: isso. O prompt completo está no comentário fixado.",
    pauses: [{ after: "Resultado: isso.", seconds: 0.8 }] }];
  let saved: Project | null = null;
  await page.route("**/api/projects", (route) => route.fulfill({ json: [project] }));
  await page.route(`**/api/projects/${id}`, (route) => {
    if (route.request().method() === "PUT") {
      saved = { ...project, ...JSON.parse(route.request().postData()!), revision: project.revision + 1 };
      return route.fulfill({ json: saved });
    }
    return route.fulfill({ json: saved || project });
  });
  await page.context().grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.goto(`/#/producoes/${id}`);
  const style = page.getByRole("region", { name: "Estilo gerado" });
  await expect(style).toContainText("#0B2A33");
  await expect(style).toContainText("#F2B544");
  await expect(style).toContainText("Roboto");
  await expect(style).toContainText("3 palavras por vez");
  await expect(style).toContainText("Loop");
  await page.getByRole("tab", { name: "Roteiro" }).click();
  await expect(page.getByText("Pausa de 0,8 s depois de “Resultado: isso.”")).toBeVisible();
  await page.getByRole("tab", { name: "Publicação" }).click();
  const titles = page.getByRole("list", { name: "Opções de título" });
  await expect(titles.getByRole("listitem")).toHaveCount(2);
  await titles.getByRole("button", { name: "Usar o título “Da ideia ao filme com IA em 4 etapas”" }).click();
  await expect(page.getByLabel("Título no YouTube")).toHaveValue("Da ideia ao filme com IA em 4 etapas");
  await expect(page.getByText("#Shorts #IA #FilmeComIA")).toBeVisible();
  await page.getByRole("button", { name: "Copiar comentário fixado" }).click();
  await expect(page.getByRole("button", { name: "Copiar comentário fixado" })).toContainText("Copiado");
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(project.publication!.pinned_comment);
  await expect
    .poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth))
    .toBe(true);
  await page.screenshot({ path: info.outputPath("free-publication.png"), fullPage: true });
  await page.getByRole("button", { name: "Salvar" }).first().click();
  await expect.poll(() => saved?.title).toBe("Da ideia ao filme com IA em 4 etapas");
  // The pauses travel with the scenes, so saving never drops them.
  expect(saved!.scenes[0].pauses).toEqual([{ after: "Resultado: isso.", seconds: 0.8 }]);
});
