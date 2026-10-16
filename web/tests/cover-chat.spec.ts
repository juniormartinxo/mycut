import { expect, test, type Page } from "@playwright/test";
import { builtApp } from "./fixtures/builtApp";
import type { CoverMessage, Project } from "../src/types";

// UI contract with explicit API fixtures. Real runner, CLIs and image decoding are covered in Python.
const id = "1234567890abcdef1234567890abcdef";
const message = "abcdefabcdefabcdefabcdefabcdef12";
const png = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
  "base64",
);
const zero = {
  input: 0,
  cache_read: 0,
  cache_write: 0,
  output: 0,
  reasoning: 0,
  web_searches: 0,
  credits: 0,
  usd: 0,
  unpriced: 0,
};
function fixture(): Project {
  return {
    id,
    title: "Agentes na nuvem",
    brief: "",
    description: "",
    tags: "",
    sources: "",
    accent: "#bd4b28",
    accent_locked: true,
    revision: 3,
    created_at: 0,
    updated_at: 0,
    scenes: [
      {
        title: "Início",
        narration: "Agentes trabalham enquanto você revisa.",
        layout: "flow",
        items: ["Pedido", "Resultado"],
      },
    ],
    jobs: [],
    audio_matches_script: true,
    usage_total: zero,
  };
}

async function api(page: Page) {
  let project = fixture();
  let messages: CoverMessage[] = [];
  const sent: string[] = [];
  const chosen: Record<string, unknown>[] = [];
  await builtApp(page);
  await page.route("**/api/integrations", (route) =>
    route.fulfill({
      json: {
        agents: {
          research: { provider: "grok", model: "" },
          writer: { provider: "claude", model: "" },
          director: { provider: "codex", model: "" },
          reviewer: { provider: "codex", model: "" },
          art: { provider: "codex", model: "" },
        },
        runner: {
          online: true,
          protocol: 4,
          providers: { codex: true, claude: true, grok: true },
          browser: { enabled: false, available: false, version: "" },
        },
        agent_models: {
          codex: {
            models: [{ id: "gpt-6-astra", name: "GPT-6 Astra" }],
            checked_at: 1,
            source: "cli",
            error: "",
          },
          claude: { models: [], checked_at: 1, source: "cli", error: "" },
          grok: { models: [], checked_at: 1, source: "cli", error: "" },
        },
        elevenlabs: { connected: false, voice_id: "" },
      },
    }),
  );
  await page.route("**/api/projects", (route) =>
    route.fulfill({ json: [project] }),
  );
  await page.route(`**/api/projects/${id}`, (route) =>
    route.fulfill({ json: project }),
  );
  await page.route(`**/api/projects/${id}/cover/messages`, async (route) => {
    if (route.request().method() === "POST") {
      sent.push(route.request().postDataBuffer()?.toString("utf8") ?? "");
      messages = [
        {
          id: message,
          created_at: 1,
          state: "running",
          status: "Codex criando a imagem",
          provider: "codex",
          model: "gpt-6-astra",
          text: "Fundo escuro com um robô laranja",
          attachments: [
            { name: "logo.png", url: `/api/projects/${id}/cover/${message}/attachments/1.png` },
          ],
          reply: "",
          images: [],
        },
      ];
      return route.fulfill({ status: 202, json: messages[0] });
    }
    const current = messages;
    // The next poll finds the generation finished.
    messages = messages.map((m) => ({
      ...m,
      state: "succeeded",
      status: "Imagem pronta",
      reply: "Criei um robô laranja sobre fundo escuro.",
      images: [
        {
          id: "1",
          width: 1080,
          height: 1920,
          url: `/api/projects/${id}/cover/${message}/images/1.png`,
        },
      ],
    }));
    return route.fulfill({ json: current });
  });
  await page.route(`**/api/projects/${id}/cover/${message}/**`, (route) =>
    route.fulfill({ contentType: "image/png", body: png }),
  );
  await page.route(`**/api/projects/${id}/assets/cover**`, (route) =>
    route.fulfill({ contentType: "image/png", body: png }),
  );
  await page.route(`**/api/projects/${id}/cover/select`, (route) => {
    chosen.push(route.request().postDataJSON());
    project = {
      ...project,
      revision: project.revision + 1,
      cover: {
        name: "Capa criada no chat · Codex",
        url: `/api/projects/${id}/assets/cover?v=4`,
        sha256: "",
        chat_image: `${message}/1`,
      },
    };
    return route.fulfill({ json: project });
  });
  return { sent, chosen };
}

test("áudio e capa são abas separadas e links antigos abrem o Áudio", async ({
  page,
}) => {
  await api(page);
  await page.goto(`/#/producoes/${id}/media`);
  const tabs = page.getByRole("tablist", { name: "Etapas da produção" });
  await expect(tabs.getByRole("tab", { name: "Áudio" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await expect(tabs.getByRole("tab", { name: "Voz e capa" })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Uma voz. Sua identidade." })).toBeVisible();
  await expect(page.getByText("Capa do Short")).toHaveCount(0);
  await tabs.getByRole("tab", { name: "Capa" }).click();
  await expect(page).toHaveURL(new RegExp(`/producoes/${id}/cover$`));
  await expect(page.getByLabel("Chat da capa")).toBeVisible();
});

test("conversar com o agente escolhido, anexar uma imagem e usar o resultado como capa", async ({
  page,
}, testInfo) => {
  const { sent, chosen } = await api(page);
  await page.goto(`/#/producoes/${id}/cover`);
  await expect(page.getByText("Descreva a capa que você imagina")).toBeVisible();
  const agent = page.getByLabel("Agente da capa", { exact: true });
  await expect(agent).toHaveValue("grok");
  await agent.selectOption("claude");
  await expect(page.getByText("ele desenha a capa em SVG")).toBeVisible();
  await agent.selectOption("codex");
  await page.getByLabel("Modelo do agente da capa").selectOption("gpt-6-astra");
  await page.getByLabel("Anexar imagens").setInputFiles({
    name: "logo.png",
    mimeType: "image/png",
    buffer: png,
  });
  await expect(page.getByLabel("Imagens anexadas")).toContainText("logo.png");
  const send = page.getByRole("button", { name: "Enviar" });
  await expect(send).toBeDisabled();
  await page
    .getByLabel("Mensagem para o agente da capa")
    .fill("Fundo escuro com um robô laranja");
  await send.click();
  await expect(page.getByText("Codex criando a imagem")).toBeVisible();
  expect(sent[0]).toContain("Fundo escuro com um robô laranja");
  expect(sent[0]).toContain('name="provider"\r\n\r\ncodex');
  expect(sent[0]).toContain('name="model"\r\n\r\ngpt-6-astra');
  expect(sent[0]).toContain('filename="logo.png"');
  await expect(page.getByLabel("Imagens anexadas")).toHaveCount(0);
  await expect(
    page.getByText("Criei um robô laranja sobre fundo escuro."),
  ).toBeVisible();
  await expect
    .poll(() =>
      page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    )
    .toBe(true);
  await page.screenshot({
    path: testInfo.outputPath("cover-chat.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "Usar como capa" }).click();
  await expect(page.getByText("Capa atual", { exact: true })).toBeVisible();
  expect(chosen).toEqual([{ job_id: message, image_id: "1", revision: 3 }]);
  await expect(page.getByText("Capa criada no chat · Codex")).toBeVisible();
  // The last agent used stays selected for the next message.
  await expect(page.getByLabel("Agente da capa", { exact: true })).toHaveValue("codex");
});
