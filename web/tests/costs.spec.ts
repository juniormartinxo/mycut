import { expect, test } from "@playwright/test";
import type { ProjectUsage, UsageCall } from "../src/types";

const call = (values: Partial<UsageCall>): UsageCall => ({
  step: "research",
  attempt: 1,
  provider: "claude",
  requested_model: "",
  model: "claude-sonnet-5-5",
  state: "succeeded",
  created_at: Date.now() / 1000,
  input: 0,
  cache_read: 0,
  cache_write: 0,
  output: 0,
  reasoning: 0,
  web_searches: 0,
  credits: null,
  usd: null,
  cost_source: null,
  ...values,
});

// Real project and editor; the usage endpoint is a fixture so every line type is visible.
test("ver o consumo discriminado de um projeto", async ({ page, request }) => {
  const project = await (
    await request.post("/api/projects", { data: { title: "Custos do Short" } })
  ).json();
  const total = {
    input: 601010,
    cache_read: 404000,
    cache_write: 2000,
    output: 21100,
    reasoning: 5150,
    web_searches: 1,
    credits: 321,
    usd: 7.464,
    unpriced: 1,
  };
  const usage: ProjectUsage = {
    total,
    usd_brl: 5,
    checked_at: "2026-10-14",
    source: "https://developers.openai.com/api/docs/pricing",
    versions: [
      {
        id: "a".repeat(32),
        kind: "pipeline",
        state: "succeeded",
        created_at: Date.now() / 1000,
        recorded: true,
        total,
        calls: [
          call({
            input: 10,
            cache_read: 4000,
            cache_write: 2000,
            output: 900,
            web_searches: 1,
            usd: 0.05,
            cost_source: "cli",
            step: "writer",
          }),
          call({
            step: "director",
            provider: "codex",
            model: "gpt-6-astra",
            input: 600000,
            cache_read: 400000,
            output: 20000,
            reasoning: 5000,
            usd: 7.4,
            cost_source: "tabela",
          }),
          call({
            step: "reviewer",
            attempt: 2,
            provider: "codex",
            model: "modelo-sem-preco",
            input: 1000,
            output: 200,
          }),
          call({
            step: "research",
            provider: "grok",
            model: "",
            state: "interrupted",
            unreported: true,
          }),
          call({
            step: "voice",
            provider: "elevenlabs",
            model: "eleven_multilingual_v2",
            credits: 321,
            credits_estimated: false,
          }),
        ],
      },
      {
        id: "b".repeat(32),
        kind: "plan",
        state: "failed",
        created_at: Date.now() / 1000 - 3600,
        recorded: false,
        calls: [],
        total: { ...total, usd: 0, credits: 0, unpriced: 0 },
      },
    ],
  };
  await page.route(`**/api/projects/${project.id}/usage`, (route) =>
    route.fulfill({ json: usage }),
  );
  await page.goto(`/#/producoes/${project.id}/costs`);
  await expect(
    page.getByRole("heading", { name: "Quanto este projeto consumiu" }),
  ).toBeVisible();
  await expect(page.getByText("US$ 7,46").first()).toBeVisible();
  await expect(page.getByText("R$ 37,32").first()).toBeVisible();
  await expect(page.getByText("1 chamada ficou sem preço")).toBeVisible();
  const rows = page.locator(".cost-table tbody tr");
  await expect(rows).toHaveCount(5);
  await expect(rows.nth(1)).toContainText("gpt-6-astra");
  await expect(rows.nth(1)).toContainText("600.000");
  await expect(rows.nth(1)).toContainText("tabela de preços");
  await expect(rows.nth(2)).toContainText("2ª tentativa");
  await expect(rows.nth(2)).toContainText("sem preço");
  await expect(rows.nth(3)).toContainText("interrompida");
  await expect(rows.nth(3)).toContainText("O CLI não informou o consumo");
  await expect(rows.nth(4)).toContainText("321 créditos");
  await expect(
    page.getByText("Consumo não registrado", { exact: false }),
  ).toBeVisible();
  // Wide tables scroll inside their own box, never the page.
  await expect
    .poll(() =>
      page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    )
    .toBe(true);
});

test("editar os preços do Codex e as conversões", async ({ page }) => {
  // Desktop and mobile share the server: start each run from a known table.
  await page.request.put("/api/integrations/pricing", {
    data: {
      usd_brl: 5.0096,
      elevenlabs_usd_per_1k_credits: null,
      models: {
        "gpt-6-astra": { input: 10, cache_read: 1, output: 50 },
        "gpt-6-luna": { input: 0.1, cache_read: 0.01, output: 0.5 },
      },
    },
  });
  await page.goto("/#/configuracoes/custos");
  const rate = page.getByRole("textbox", {
    name: "Cotação do dólar (R$ por US$ 1)",
  });
  await expect(rate).toHaveValue("5.0096");
  await expect(
    page.getByRole("textbox", { name: "gpt-6-astra: saída" }),
  ).toHaveValue("50");
  await rate.fill("5,25");
  await page
    .getByRole("textbox", { name: "ElevenLabs: US$ por 1.000 créditos" })
    .fill("0,30");
  await page.getByRole("button", { name: "Adicionar modelo" }).click();
  const rows = page.locator(".pricing-form tbody tr");
  const added = rows.last();
  await added.getByRole("textbox", { name: "Modelo" }).fill("gpt-teste");
  await added
    .getByRole("textbox", { name: "gpt-teste: entrada", exact: true })
    .fill("1");
  await added
    .getByRole("textbox", { name: "gpt-teste: entrada em cache" })
    .fill("0,1");
  await added.getByRole("textbox", { name: "gpt-teste: saída" }).fill("2");
  await page.getByRole("button", { name: "Remover gpt-6-luna" }).click();
  await page.getByRole("button", { name: "Salvar preços" }).click();
  await expect(
    page.getByText("Preços salvos.", { exact: false }),
  ).toBeVisible();
  const saved = await (await page.request.get("/api/integrations")).json();
  expect(saved.pricing.usd_brl).toBe(5.25);
  expect(saved.pricing.elevenlabs_usd_per_1k_credits).toBe(0.3);
  expect(saved.pricing.models["gpt-teste"]).toEqual({
    input: 1,
    cache_read: 0.1,
    output: 2,
  });
  expect(saved.pricing.models["gpt-6-luna"]).toBeUndefined();
  await expect
    .poll(() =>
      page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    )
    .toBe(true);
});
