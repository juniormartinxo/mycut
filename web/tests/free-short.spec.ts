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
          ["research", "writer", "director", "reviewer", "art"].map((role) => [
            role,
            { provider: "codex", model: "" },
          ]),
        ),
        pricing: { images: { codex: 0.05, grok: 0.05 } },
        runner: { online: true, protocol: 4, providers: { codex: true } },
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
  await expect(page.getByText("não aplicada")).toHaveCount(0);
  // Editing the passage away leaves the pause without effect: the voice has no silence there, and the user is told.
  await page.getByLabel("Narração da cena 1").fill("Resultado: pronto. O prompt completo está no comentário fixado.");
  await expect(page.getByText("Pausa de 0,8 s depois de “Resultado: isso.” · não aplicada: o trecho não está na narração")).toBeVisible();
  await page.getByLabel("Narração da cena 1").fill(project.scenes[0].narration);
  await expect(page.getByText("não aplicada")).toHaveCount(0);
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

test("A Arte gera primeiro as imagens-base e deixa orientar cada uma antes das demais", async ({ page }, info) => {
  await builtApp(page);
  await agents(page);
  // In /#/novo, Livre asks what the Arte generates and shows the ceiling of the estimate.
  let created: Record<string, unknown> | null = null;
  await page.route("**/api/projects/free", (route) => {
    const body = route.request().postDataBuffer()!.toString("utf8");
    created = JSON.parse(body.split('name="project"')[1].split("\r\n\r\n")[1].split("\r\n--")[0]);
    return route.fulfill({ status: 201, json: project });
  });
  const base = "a1b2c3d4e5f60718293a4b5c6d7e8f90";
  const project: Project = {
    ...freeProject(prompt),
    images: [{ id: base, name: "Ficha da Comandante Ira Vale", url: `/api/projects/${id}/images/${base}`, width: 96,
      height: 64, source_url: "", page_url: "" }],
    art: {
      mode: "bases",
      then: "pipeline",
      estimate: { images: 2, provider: "codex", usd_per_image: 0.05, usd: 0.1 },
      bible: {
        tone: "Ficção científica intimista: azul-petróleo frio contra o âmbar quente da flor.",
        sheets: [{ kind: "character", name: "Comandante Ira Vale", description: "38 anos, cicatriz na sobrancelha esquerda." }],
      },
      requests: [
        { key: "ira", base: true, title: "Ficha da Comandante Ira Vale", prompt: "Studio character reference sheet",
          references: [], aspect: "3:2", state: "generated", image_id: base, error: "", messages: [], outdated: false },
        { key: "ira-corredor", base: false, title: "Ira avança pelo corredor", prompt: "Medium shot, 50mm lens",
          references: ["ira"], aspect: "9:16", state: "pending", image_id: null, error: "", messages: [], outdated: false },
      ],
    },
  };
  await page.route("**/api/projects", (route) => route.fulfill({ json: [project] }));
  await page.route(`**/api/projects/${id}`, (route) => route.fulfill({ json: project }));
  await page.route(`**/api/projects/${id}/images/${base}`, (route) =>
    route.fulfill({ body: png, contentType: "image/png" }));
  const posted: { url: string; body: string }[] = [];
  await page.route(`**/api/projects/${id}/art**`, (route) => {
    posted.push({ url: route.request().url(), body: route.request().postDataBuffer()!.toString("utf8") });
    return route.fulfill({ status: 202, json: { id: "f".repeat(32), kind: "art" } });
  });
  await page.goto("/#/novo");
  await page.getByRole("radio", { name: "Livre", exact: true }).check();
  const arte = page.getByRole("group", { name: "Imagens da Arte" });
  await expect(arte.getByRole("radio", { name: /Conferir as imagens-base primeiro/ })).toBeChecked();
  await expect(arte).toContainText("Até 12 imagens com Codex · estimativa de até US$ 0,60 (US$ 0,05 por imagem)");
  await arte.getByRole("radio", { name: /Gerar todas as imagens/ }).check();
  await page.getByLabel("Prompt do Short livre").fill("Uma astronauta encontra uma flor alienígena.");
  await page.getByRole("button", { name: "Produzir com agentes" }).click();
  await expect.poll(() => created?.art).toBe("all");
  // The Arte tab: the bible, the base to review and guide, and the remaining image with its estimate.
  await page.goto(`/#/producoes/${id}/art`);
  const bible = page.getByRole("region", { name: "Bíblia visual" });
  await expect(bible).toContainText("azul-petróleo frio");
  await expect(bible).toContainText("Personagem · Comandante Ira Vale");
  const bases = page.getByRole("region", { name: "Imagens-base" });
  await expect(bases.getByRole("img", { name: "Ficha da Comandante Ira Vale" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Imagens das cenas" })).toContainText("Aguardando geração · 9:16 · com Ficha da Comandante Ira Vale");
  // A scene image waits for its bases: it cannot be guided before they exist.
  project.art!.requests[0] = { ...project.art!.requests[0], state: "failed", image_id: null };
  await page.reload();
  const scenes = page.getByRole("region", { name: "Imagens das cenas" });
  await expect(scenes).toContainText("Gere antes a imagem-base “Ficha da Comandante Ira Vale”");
  await expect(scenes.getByLabel("Orientação para a Arte")).toBeDisabled();
  project.art!.requests[0] = { ...project.art!.requests[0], state: "generated", image_id: base };
  await page.reload();
  await expect(page.getByText("1 imagem · estimativa US$ 0,05.")).toBeVisible();
  await bases.getByLabel("Orientação para a Arte").fill("Cicatriz bem visível");
  await bases.locator("input[type=file]").setInputFiles({ name: "exemplo.png", mimeType: "image/png", buffer: png });
  await expect(bases.getByRole("list", { name: "Exemplos para Ficha da Comandante Ira Vale" })).toContainText("exemplo.png");
  await expect
    .poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth))
    .toBe(true);
  await page.screenshot({ path: info.outputPath("free-art.png"), fullPage: true });
  await bases.getByRole("button", { name: "Refazer com esta orientação · estimativa US$ 0,05" }).click();
  await expect.poll(() => posted.length).toBe(1);
  expect(posted[0].url).toContain(`/api/projects/${id}/art/ira`);
  expect(posted[0].body).toContain("Cicatriz bem visível");
  expect(posted[0].body).toContain('filename="exemplo.png"');
  await page.getByRole("button", { name: "Gerar a imagem que falta e continuar a produção" }).click();
  await expect.poll(() => posted.length).toBe(2);
  expect(posted[1].url).toMatch(/\/art$/);
  expect(JSON.parse(posted[1].body)).toEqual({ revision: 2 });
});
