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
    },
    runner: {
      online: true,
      protocol: 2,
      providers: { codex: true, claude: true, grok: true },
    },
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
    .getByRole("button", { name: "Conexões", exact: true })
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
    .getByRole("button", { name: "Conexões", exact: true })
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
