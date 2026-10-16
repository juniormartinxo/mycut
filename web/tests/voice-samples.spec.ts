import { expect, test, type Page } from "@playwright/test";
import { readFile } from "node:fs/promises";
import { basename, extname } from "node:path";
import type { Integrations, VoiceCatalog, VoiceTest } from "../src/types";

// Synthetic audio and provider API fixtures. Never connects to ElevenLabs.
function sample() {
  const bytes = Buffer.alloc(44 + 16000);
  bytes.write("RIFF", 0);
  bytes.writeUInt32LE(bytes.length - 8, 4);
  bytes.write("WAVEfmt ", 8);
  bytes.writeUInt32LE(16, 16);
  bytes.writeUInt16LE(1, 20);
  bytes.writeUInt16LE(1, 22);
  bytes.writeUInt32LE(8000, 24);
  bytes.writeUInt32LE(16000, 28);
  bytes.writeUInt16LE(2, 32);
  bytes.writeUInt16LE(16, 34);
  bytes.write("data", 36);
  bytes.writeUInt32LE(16000, 40);
  return bytes;
}

async function setup(page: Page, brokenPreview = false) {
  // Serve the actual built app without a listening socket; all APIs are fixtures.
  await page.route("**/*", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/health")
      return route.fulfill({
        json: { status: "ok", worker_online: false, ffmpeg: true },
      });
    if (path === "/api/projects") return route.fulfill({ json: [] });
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
        body: await readFile(new URL(`../dist/${file}`, import.meta.url)),
        contentType: mime[extname(file)],
      });
    }
    return route.abort();
  });
  const empty = { models: [], source: "", checked_at: null, error: "" };
  const settings: Integrations = {
    agents: {
      research: { provider: "grok", model: "" },
      writer: { provider: "claude", model: "" },
      director: { provider: "codex", model: "" },
      reviewer: { provider: "codex", model: "" },
      art: { provider: "codex", model: "" },
    },
    commands: { codex: "codex", claude: "claude", grok: "grok" },
    runner: {
      online: false,
      protocol: 2,
      providers: { codex: false, claude: false, grok: false },
      browser: { enabled: false, available: false, version: "" },
    },
    browser: { enabled: true, chrome_path: "", port: 9222 },
    browser_test: null,
    pricing: { usd_brl: 5, elevenlabs_usd_per_1k_credits: null, models: {} },
    agent_models: { codex: empty, claude: empty, grok: empty },
    elevenlabs: {
      connected: true,
      voice_id: "junior",
      voice_name: "Junior",
      model_id: "model-a",
      stability: 0.5,
      similarity_boost: 0.75,
      speed: 1,
    },
  };
  const catalog: VoiceCatalog = {
    voices: [
      {
        id: "junior",
        name: "Junior",
        category: "cloned",
        language: "pt",
        accent: "pt-brazilian",
        preview_url: "https://audio.example/sample.mp3",
      },
      {
        id: "other",
        name: "Outra voz",
        category: "cloned",
        preview_url: null,
        language: "pt",
        accent: "brazilian",
      },
      {
        id: "english",
        name: "English voice",
        category: "premade",
        preview_url: null,
        language: "en",
        accent: "american",
      },
      {
        id: "spanish",
        name: "Voz espanhola",
        category: "premade",
        preview_url: null,
        language: "es",
      },
      {
        id: "unknown",
        name: "Voz sem idioma",
        category: "cloned",
        preview_url: null,
        language: null,
      },
    ],
    models: [
      { id: "model-a", name: "Modelo A" },
      { id: "model-b", name: "Modelo B" },
    ],
  };
  const generated: { text: string; settings: VoiceTest["settings"] }[] = [];
  let history: VoiceTest[] = [];
  let paidFailure = false;
  await page.route("**/api/integrations", (route) =>
    route.fulfill({ json: settings }),
  );
  await page.route("**/api/integrations/agents/tests", (route) =>
    route.fulfill({ json: {} }),
  );
  await page.route("**/api/integrations/elevenlabs/catalog", (route) =>
    route.fulfill({ json: catalog }),
  );
  await page.route("https://audio.example/sample.mp3", (route) =>
    brokenPreview
      ? route.fulfill({ status: 404 })
      : route.fulfill({ contentType: "audio/wav", body: sample() }),
  );
  await page.route("**/api/integrations/elevenlabs/tests", async (route) => {
    if (route.request().method() === "GET")
      return route.fulfill({ json: history });
    const body = route.request().postDataJSON();
    generated.push(body);
    if (paidFailure)
      return route.fulfill({
        status: 422,
        json: { detail: "Créditos insuficientes." },
      });
    const result: VoiceTest = {
      ...body,
      id: "fixture",
      voice_name: "Outra voz",
      model_name: "Modelo B",
      created_at: Date.now() / 1000,
      duration: 1,
      cached: false,
      url: "/api/integrations/elevenlabs/tests/fixture/audio",
    };
    history = [result];
    return route.fulfill({ json: result });
  });
  await page.route("**/api/integrations/elevenlabs/tests/*/audio", (route) =>
    route.fulfill({ contentType: "audio/wav", body: sample() }),
  );
  await page.goto("/#/configuracoes/vozes");
  await expect(
    page.getByRole("combobox", { name: "Voz", exact: true }),
  ).toHaveValue("junior");
  return {
    generated,
    catalog,
    fail: () => {
      paidFailure = true;
    },
  };
}

test("configurações separam áreas, preservam rascunhos e mantêm a seção no histórico", async ({
  page,
}, testInfo) => {
  const { generated } = await setup(page);
  const menus = page.getByRole("navigation", {
    name: "Seções de configurações",
  });
  await expect(menus).toHaveCount(1);
  await expect(
    page.getByRole("heading", { name: "Vozes", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Agentes no seu computador" }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("heading", { name: "Comandos dos CLIs" }),
  ).toHaveCount(0);
  const connectionKey = page.getByLabel("Chave de API da ElevenLabs");
  await expect(connectionKey).toBeHidden();
  await page.getByText("Gerenciar conexão", { exact: true }).click();
  await expect(connectionKey).toHaveAttribute("type", "password");
  await expect(connectionKey).toBeVisible();
  await page.getByText("Gerenciar conexão", { exact: true }).click();
  const language = page.getByRole("combobox", { name: "Idioma da voz" });
  const voice = page.getByRole("combobox", { name: "Voz", exact: true });
  const model = page.getByRole("combobox", { name: "Modelo de voz" });
  const boxes = await Promise.all(
    [language, voice, model].map((field) => field.boundingBox()),
  );
  expect(
    boxes.every((box) => box && box.height >= 40 && box.height <= 44),
  ).toBe(true);
  if (testInfo.project.name === "desktop") {
    expect(boxes[0]!.width).toBeLessThan(250);
    expect(boxes[0]!.y).toBe(boxes[1]!.y);
    expect(boxes[1]!.y).toBe(boxes[2]!.y);
  }
  await page.screenshot({
    path: testInfo.outputPath("settings-voices.png"),
    fullPage: true,
  });
  await model.selectOption("model-b");
  await menus.getByRole("button", { name: "Ambiente", exact: true }).click();
  await expect(page).toHaveURL(/#\/configuracoes\/ambiente$/);
  await expect(
    page.getByRole("heading", { name: "Comandos dos CLIs" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Navegador para pesquisa" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "ElevenLabs", exact: true }),
  ).toHaveCount(0);
  await expect
    .poll(() =>
      page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    )
    .toBe(true);
  await page.screenshot({
    path: testInfo.outputPath("settings-environment.png"),
    fullPage: true,
  });
  await page.goBack();
  await expect(model).toHaveValue("model-b");
  await page.goForward();
  await expect(
    page.getByRole("heading", { name: "Ambiente", exact: true }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Ambiente", exact: true }),
  ).toBeVisible();
  await menus.getByRole("button", { name: "Agentes", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Agentes no seu computador" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Comandos dos CLIs" }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("heading", { name: "ElevenLabs", exact: true }),
  ).toHaveCount(0);
  await page.reload();
  await expect(
    menus.getByRole("button", { name: "Agentes", exact: true }),
  ).toHaveAttribute("aria-current", "page");
  await page.goto("/#/conexoes");
  await expect(page).toHaveURL(/#\/configuracoes\/agentes$/);
  expect(generated).toHaveLength(0);
});

test("ouvir amostra grátis, gerar com a seleção atual e reouvir após refresh", async ({
  page,
}, testInfo) => {
  const { generated } = await setup(page);
  const preview = page.getByLabel("Amostra gratuita de Junior");
  await expect(preview).toHaveAttribute("preload", "none");
  await page.getByRole("button", { name: "Ouvir amostra · grátis" }).click();
  await expect
    .poll(() =>
      preview.evaluate((audio: HTMLAudioElement) => audio.currentTime),
    )
    .toBeGreaterThan(0);
  expect(generated).toHaveLength(0);
  await page
    .getByRole("combobox", { name: "Voz", exact: true })
    .selectOption("other");
  await expect(
    page.getByRole("button", { name: "Ouvir amostra · grátis" }),
  ).toBeDisabled();
  await expect(
    page.getByText(/Esta voz não tem uma amostra pronta/),
  ).toBeVisible();
  expect(generated).toHaveLength(0);
  await page
    .getByRole("combobox", { name: "Modelo de voz", exact: true })
    .selectOption("model-b");
  const speed = page.getByRole("slider", { name: /Velocidade/ });
  await speed.focus();
  await speed.press("ArrowLeft");
  await speed.press("ArrowLeft");
  const text = page.getByRole("textbox", { name: "Texto do teste" });
  await text.fill("Uma fala curta para comparar.");
  await expect(
    page.getByText(/Gerar uma fala nova consome créditos/),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Gerar teste (usa créditos)" })
    .click();
  await expect(
    page.getByText("Teste gerado e salvo.", { exact: false }),
  ).toBeVisible();
  expect(generated).toEqual([
    {
      text: "Uma fala curta para comparar.",
      settings: {
        voice_id: "other",
        model_id: "model-b",
        stability: 0.5,
        similarity_boost: 0.75,
        speed: 0.9,
      },
    },
  ]);
  const saved = page.getByLabel("Teste salvo de Outra voz com Modelo B");
  await saved.evaluate((audio: HTMLAudioElement) => audio.play());
  await expect
    .poll(() => saved.evaluate((audio: HTMLAudioElement) => audio.currentTime))
    .toBeGreaterThan(0);
  await page.reload();
  await expect(saved).toBeVisible();
  expect(generated).toHaveLength(1);
  await expect(
    page.getByRole("combobox", { name: "Voz", exact: true }),
  ).toHaveValue("junior");
  await expect(
    page.getByText(/Velocidade 0,?\.9|Velocidade 0.90/),
  ).toBeVisible();
  await page
    .getByRole("heading", { name: "Testar com meu texto" })
    .scrollIntoViewIfNeeded();
  await expect
    .poll(() =>
      page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    )
    .toBe(true);
  await page.screenshot({
    path: testInfo.outputPath("voice-samples.png"),
    fullPage: true,
  });
});

test("filtrar idioma antes da voz, preservar a preferência e distinguir idioma ausente", async ({
  page,
}, testInfo) => {
  const { generated, catalog } = await setup(page);
  const language = page.getByRole("combobox", {
    name: "Idioma da voz",
    exact: true,
  });
  const voice = page.getByRole("combobox", { name: "Voz", exact: true });
  const generate = page.getByRole("button", {
    name: "Gerar teste (usa créditos)",
  });
  await expect(language).toHaveValue("pt");
  await expect(voice.getByRole("option")).toHaveCount(3);
  await expect(
    voice.getByRole("option", { name: /Junior · Português · Brasileiro/ }),
  ).toHaveCount(1);
  await expect(
    voice.getByRole("option", { name: /English voice/ }),
  ).toHaveCount(0);
  await language.selectOption("en");
  await expect(voice).toHaveValue("");
  await expect(generate).toBeDisabled();
  await expect(
    page.getByRole("button", { name: "Salvar voz", exact: true }),
  ).toBeDisabled();
  await expect(
    voice.getByRole("option", { name: /English voice · Inglês · Americano/ }),
  ).toHaveCount(1);
  await voice.selectOption("english");
  await expect(generate).toBeEnabled();
  await page.reload();
  await expect(language).toHaveValue("en");
  await expect(
    page.getByText("A voz atual está fora deste filtro.", { exact: false }),
  ).toBeVisible();
  await expect(voice).toHaveValue("junior"); // Saved voice was never replaced by filtering.
  await expect(generate).toBeDisabled();
  await language.selectOption("unknown");
  await expect(voice.getByRole("option")).toHaveCount(2);
  await expect(
    voice.getByRole("option", {
      name: /Voz sem idioma · Idioma não informado/,
    }),
  ).toHaveCount(1);
  await language.selectOption("all");
  await expect(voice.getByRole("option")).toHaveCount(6);
  await language.selectOption("pt");
  await voice.selectOption("junior");
  await expect
    .poll(() =>
      page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    )
    .toBe(true);
  await page
    .locator(".connection-section")
    .filter({
      has: page.getByRole("heading", { name: "ElevenLabs", exact: true }),
    })
    .screenshot({ path: testInfo.outputPath("voice-language.png") });
  catalog.voices = catalog.voices.filter((v) => v.language !== "pt");
  await page.getByRole("button", { name: "Atualizar vozes e modelos" }).click();
  await expect(
    page.getByText("Nenhuma voz neste idioma.", { exact: false }),
  ).toBeVisible();
  await expect(voice).toBeDisabled();
  await expect(generate).toBeDisabled();
  expect(generated).toHaveLength(0);
});

test("amostra indisponível e texto vazio não disparam geração", async ({
  page,
}) => {
  const { generated } = await setup(page, true);
  await page.getByRole("button", { name: "Ouvir amostra · grátis" }).click();
  await expect(
    page.getByRole("alert").filter({ hasText: /amostra/ }),
  ).toBeVisible();
  expect(generated).toHaveLength(0);
  await page.getByRole("textbox", { name: "Texto do teste" }).fill("  ");
  await expect(
    page.getByRole("button", { name: "Gerar teste (usa créditos)" }),
  ).toBeDisabled();
  await expect(
    page.getByRole("textbox", { name: "Texto do teste" }),
  ).toHaveAttribute("maxlength", "300");
});

test("falha na geração é exibida sem repetição automática", async ({
  page,
}) => {
  const { generated, fail } = await setup(page);
  fail();
  await page
    .getByRole("button", { name: "Gerar teste (usa créditos)" })
    .click();
  await expect(
    page.getByRole("alert").filter({ hasText: "Créditos insuficientes" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Gerar teste (usa créditos)" }),
  ).toBeEnabled();
  expect(generated).toHaveLength(1);
});
