import { expect, test } from "@playwright/test";
import type { AgentRole, AgentTest, Integrations } from "../src/types";

// UI contracts with explicit API fixtures. Real ASGI/runner boundaries are covered in Python.
test("selecionar IDs, testar o rascunho, recarregar e distinguir outro modelo", async ({
  page,
}, testInfo) => {
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
      online: true,
      protocol: 3,
      providers: { codex: true, claude: true, grok: true },
      browser: { enabled: true, available: false, version: "" },
    },
    browser: { enabled: true, chrome_path: "", port: 9222 },
    browser_test: null,
    pricing: { usd_brl: 5, elevenlabs_usd_per_1k_credits: null, models: {} },
    agent_models: {
      codex: {
        models: [{ id: "codex-fixture", name: "Codex de teste" }],
        source: "cache",
        checked_at: Date.now() / 1000,
        error: "",
      },
      claude: {
        models: [{ id: "claude-fixture", name: "Claude de teste" }],
        source: "cli",
        checked_at: Date.now() / 1000,
        error: "",
      },
      grok: {
        models: [{ id: "grok-fixture", name: "Grok de teste" }],
        source: "cache",
        checked_at: Date.now() / 1000,
        error: "",
      },
    },
    elevenlabs: {
      connected: false,
      voice_id: "",
      voice_name: "",
      model_id: "",
      stability: 0.5,
      similarity_boost: 0.75,
      speed: 1,
    },
  };
  const latest: Partial<Record<AgentRole, AgentTest>> = {};
  let requested: unknown;
  await page.route("**/api/integrations", (route) =>
    route.fulfill({ json: settings }),
  );
  await page.route("**/api/integrations/agents/tests", async (route) => {
    if (route.request().method() === "GET")
      return route.fulfill({ json: latest });
    const choice = route.request().postDataJSON();
    requested = choice;
    const result: AgentTest = {
      ...choice,
      id: "fixture-test",
      state: "succeeded",
      created_at: Date.now() / 1000,
      elapsed: 1.2,
      reply: "Recebi o desafio de teste.",
      reported_models: ["another-fixture"],
      verification: "mismatch",
      error: "",
    };
    latest[choice.role as AgentRole] = result;
    return route.fulfill({ status: 202, json: result });
  });
  await page.goto("/");
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Configurações", exact: true })
    .click();
  const model = page.getByRole("combobox", {
    name: "Modelo de Roteiro",
    exact: true,
  });
  await model.selectOption("claude-fixture");
  await page
    .getByRole("button", { name: "Testar agente de Roteiro", exact: true })
    .click();
  await expect(
    page.getByText("Respondeu · modelo diferente do selecionado", {
      exact: true,
    }),
  ).toBeVisible();
  expect(requested).toEqual({
    role: "writer",
    provider: "claude",
    model: "claude-fixture",
  });
  expect(settings.agents.writer.model).toBe(""); // Testing never saves the draft.
  await page
    .getByRole("combobox", { name: "CLI de Roteiro", exact: true })
    .selectOption("grok");
  await expect(model).toHaveValue("");
  await expect(
    page.getByText("Resultado da seleção anterior.", { exact: false }),
  ).toBeVisible();
  await expect(
    model.getByRole("option", { name: /Claude de teste/ }),
  ).toHaveCount(0);
  await page.reload();
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Configurações", exact: true })
    .click();
  await expect(
    page.getByText("Recebi o desafio de teste.", { exact: true }),
  ).toBeVisible();
  await expect
    .poll(() =>
      page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    )
    .toBe(true);
  await page.screenshot({
    path: testInfo.outputPath("agent-connections.png"),
    fullPage: true,
  });
});

test("personalizar e restaurar o comando de um CLI", async ({ page }) => {
  const empty = { models: [], source: "", checked_at: null, error: "" };
  const settings: Integrations = {
    agents: {
      research: { provider: "grok", model: "" },
      writer: { provider: "claude", model: "" },
      director: { provider: "codex", model: "" },
      reviewer: { provider: "codex", model: "" },
      art: { provider: "codex", model: "" },
    },
    commands: { codex: "codex", claude: "claude", grok: "grok-ausente" },
    runner: {
      online: true,
      protocol: 3,
      providers: { codex: true, claude: true, grok: false },
      browser: { enabled: true, available: false, version: "" },
    },
    browser: { enabled: true, chrome_path: "", port: 9222 },
    browser_test: null,
    pricing: { usd_brl: 5, elevenlabs_usd_per_1k_credits: null, models: {} },
    agent_models: { codex: empty, claude: empty, grok: empty },
    elevenlabs: {
      connected: false,
      voice_id: "",
      voice_name: "",
      model_id: "",
      stability: 0.5,
      similarity_boost: 0.75,
      speed: 1,
    },
  };
  let saved: unknown;
  await page.route("**/api/integrations", (route) =>
    route.fulfill({ json: settings }),
  );
  await page.route("**/api/integrations/agents/tests", (route) =>
    route.fulfill({ json: {} }),
  );
  await page.route("**/api/integrations/commands", (route) => {
    saved = route.request().postDataJSON();
    settings.commands = saved as Integrations["commands"];
    return route.fulfill({ json: settings });
  });
  await page.goto("/#/configuracoes/ambiente");
  const grok = page.getByRole("textbox", { name: "Comando do Grok" });
  await expect(grok).toHaveAttribute("aria-invalid", "true");
  await expect(
    page.getByText("Executável não encontrado pelo executor.", {
      exact: false,
    }),
  ).toBeVisible();
  const claude = page.getByRole("textbox", { name: "Comando do Claude Code" });
  await claude.fill("CLAUDE_CONFIG_DIR=~/.config/perfil claude");
  await expect(page.getByText("Alteração não salva.")).toBeVisible();
  await page
    .locator("label", { has: grok })
    .getByRole("button", { name: "Restaurar padrão" })
    .click();
  await expect(grok).toHaveValue("grok");
  await page.getByRole("button", { name: "Salvar comandos" }).click();
  await expect(
    page.getByText("Comandos salvos.", { exact: false }),
  ).toBeVisible();
  expect(saved).toEqual({
    codex: "codex",
    claude: "CLAUDE_CONFIG_DIR=~/.config/perfil claude",
    grok: "grok",
  });
  await expect(
    page.getByText("Comando personalizado.", { exact: false }),
  ).toBeVisible();
  await expect
    .poll(() =>
      page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    )
    .toBe(true);
});

test("configurar e testar o navegador da pesquisa", async ({ page }) => {
  const empty = { models: [], source: "", checked_at: null, error: "" };
  const settings: Integrations = {
    agents: {
      research: { provider: "claude", model: "" },
      writer: { provider: "claude", model: "" },
      director: { provider: "codex", model: "" },
      reviewer: { provider: "codex", model: "" },
      art: { provider: "codex", model: "" },
    },
    commands: { codex: "codex", claude: "claude", grok: "grok" },
    browser: { enabled: true, chrome_path: "", port: 9222 },
    browser_test: null,
    pricing: { usd_brl: 5, elevenlabs_usd_per_1k_credits: null, models: {} },
    runner: {
      online: true,
      protocol: 3,
      providers: { codex: true, claude: true, grok: true },
      browser: { enabled: true, available: false, version: "" },
    },
    agent_models: { codex: empty, claude: empty, grok: empty },
    elevenlabs: {
      connected: false,
      voice_id: "",
      voice_name: "",
      model_id: "",
      stability: 0.5,
      similarity_boost: 0.75,
      speed: 1,
    },
  };
  let saved: unknown;
  await page.route("**/api/integrations", (route) =>
    route.fulfill({ json: settings }),
  );
  await page.route("**/api/integrations/agents/tests", (route) =>
    route.fulfill({ json: {} }),
  );
  await page.route("**/api/integrations/browser", (route) => {
    saved = route.request().postDataJSON();
    settings.browser = saved as Integrations["browser"];
    return route.fulfill({ json: settings });
  });
  await page.route("**/api/integrations/browser/test", (route) => {
    // The runner answers on a later poll of /integrations.
    settings.browser_test = {
      id: "browser-fixture",
      checked_at: Date.now() / 1000,
      version: "Chrome/157.0.8102.0",
      error: "",
    };
    settings.runner.browser = {
      enabled: true,
      available: true,
      version: "Chrome/157.0.8102.0",
    };
    return route.fulfill({
      status: 202,
      json: { id: "browser-fixture", message: "" },
    });
  });
  await page.goto("/#/configuracoes/ambiente");
  await expect(
    page.getByText("Fechado. O executor abre o Chrome", { exact: false }),
  ).toBeVisible();
  const path = page.getByRole("textbox", { name: "Caminho do chrome.exe" });
  await path.fill(" C:\\Chrome\\chrome.exe ");
  const test = page.getByRole("button", { name: "Abrir e testar" });
  await expect(test).toBeDisabled(); // Testing uses saved settings.
  await page.getByRole("button", { name: "Salvar navegador" }).click();
  await expect(page.getByText("Navegador salvo.")).toBeVisible();
  expect(saved).toEqual({
    enabled: true,
    chrome_path: "C:\\Chrome\\chrome.exe",
    port: 9222,
  });
  await test.click();
  await expect(page.getByText("Navegador pronto para a pesquisa")).toBeVisible({
    timeout: 15_000,
  });
  await expect(
    page.getByText("Chrome conectado · Chrome/157.0.8102.0"),
  ).toBeVisible();
  await page
    .getByRole("checkbox", { name: "Usar o navegador na pesquisa" })
    .uncheck();
  await page.getByRole("button", { name: "Salvar navegador" }).click();
  await expect(page.getByText("Desativado.", { exact: false })).toBeVisible();
  await expect(test).toBeDisabled();
  await expect
    .poll(() =>
      page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    )
    .toBe(true);
});
