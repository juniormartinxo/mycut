import { expect, test, type Page } from "@playwright/test";
import { builtApp } from "./fixtures/builtApp";
import type { Project } from "../src/types";

const id = "1234567890abcdef1234567890abcdef";
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
    title: "Tarefas na nuvem",
    brief: "Explique tarefas na nuvem",
    description: "",
    tags: "",
    sources: "",
    accent: "#123456",
    accent_locked: true,
    revision: 1,
    created_at: 0,
    updated_at: 0,
    scenes: ["Início", "Execução", "Revisão"].map((title) => ({
      title,
      narration: `Você acompanha a etapa de ${title.toLowerCase()}.`,
      layout: "flow",
      items: [],
    })),
    jobs: [],
    audio_matches_script: true,
    usage_total: zero,
  };
}

async function settings(page: Page, allOnline: boolean) {
  await page.route("**/api/integrations", (route) =>
    route.fulfill({
      json: {
        agents: {
          research: { provider: "grok", model: "" },
          writer: { provider: "claude", model: "" },
          director: { provider: "codex", model: "" },
          reviewer: { provider: "codex", model: "" },
        },
        runner: {
          online: true,
          protocol: 3,
          providers: { codex: true, claude: allOnline, grok: allOnline },
        },
        elevenlabs: { connected: false, voice_id: "" },
      },
    }),
  );
}

test("escolher a cor antes dos agentes e preservar a escolha ao navegar", async ({
  page,
}, testInfo) => {
  await builtApp(page);
  await settings(page, true);
  let project: Project | null = null;
  let input: Record<string, unknown> = {};
  await page.route("**/api/projects", async (route) => {
    if (route.request().method() === "POST") {
      input = route.request().postDataJSON();
      project = {
        ...fixture(),
        accent: String(input.accent),
        accent_locked: true,
      };
      return route.fulfill({ status: 201, json: project });
    }
    return route.fulfill({ json: project ? [project] : [] });
  });
  await page.goto("/#/novo");
  await page
    .getByLabel("Pauta ou link")
    .fill("Como tarefas continuam na nuvem");
  await page.getByLabel("Roteiro e cenas primeiro").check();
  await page.getByLabel("Cor de destaque", { exact: true }).fill("#663399");
  await page
    .getByRole("navigation", { name: "Navegação principal" })
    .getByRole("button", { name: "Fila de produção" })
    .click();
  await page.goBack();
  await expect(page.getByLabel("Cor de destaque", { exact: true })).toHaveValue(
    "#663399",
  );
  await expect
    .poll(() =>
      page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    )
    .toBe(true);
  await page.screenshot({
    path: testInfo.outputPath("theme-before-generation.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "Criar roteiro com agentes" }).click();
  await expect(page).toHaveURL(new RegExp(`${id}$`));
  expect(input).toMatchObject({ accent: "#663399", automation: "plan" });
  await expect(page.getByLabel("Cor de destaque", { exact: true })).toHaveValue(
    "#663399",
  );
});

test("cenas incompletas podem ser refeitas pelos agentes com os ajustes atuais", async ({
  page,
}, testInfo) => {
  await builtApp(page);
  // Research/writer unavailable: only direction and review are needed here.
  await settings(page, false);
  let project = fixture();
  const calls: { path: string; input: Record<string, unknown> }[] = [];
  await page.route("**/api/projects", (route) =>
    route.fulfill({ json: [project] }),
  );
  await page.route(`**/api/projects/${id}`, (route) => {
    if (route.request().method() === "PUT") {
      const input = route.request().postDataJSON();
      calls.push({ path: "save", input });
      project = { ...project, ...input, revision: project.revision + 1 };
    }
    return route.fulfill({ json: project });
  });
  await page.route(`**/api/projects/${id}/run`, (route) => {
    calls.push({ path: "run", input: route.request().postDataJSON() });
    project = {
      ...project,
      revision: project.revision + 1,
      scenes: project.scenes.map((scene) => ({
        ...scene,
        items: ["Seu pedido", "Tarefa na nuvem", "Sua revisão"],
      })),
    };
    return route.fulfill({ status: 202, json: { id: "queued-scenes" } });
  });
  await page.goto(`/#/producoes/${id}/scenes`);
  await expect(
    page.getByText("3 cenas estão sem o conteúdo visual completo.", {
      exact: false,
    }),
  ).toBeVisible();
  await expect(
    page.getByText("Aguardando conteúdo visual", { exact: true }),
  ).toBeVisible();
  await page.getByLabel("Cor de destaque do vídeo").fill("#292e29");
  await page.getByRole("button", { name: "Criar cenas com agentes" }).click();
  await expect(
    page.getByLabel("Textos do diagrama", { exact: false }),
  ).toHaveValue("Seu pedido\nTarefa na nuvem\nSua revisão");
  expect(calls.map((call) => call.path)).toEqual(["save", "run"]);
  expect(calls[0].input).toMatchObject({
    accent: "#292e29",
    accent_locked: true,
  });
  expect(calls[1].input).toMatchObject({ kind: "scenes", revision: 2 });
  expect(project.scenes.map((s) => s.narration)).toEqual(
    fixture().scenes.map((s) => s.narration),
  );
  await expect(
    page.getByRole("button", { name: "Refazer cenas com agentes" }),
  ).toBeEnabled();
  await expect(
    page.getByText("Aguardando conteúdo visual", { exact: true }),
  ).toHaveCount(0);
  await expect
    .poll(() =>
      page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    )
    .toBe(true);
  await page.screenshot({
    path: testInfo.outputPath("scenes-from-agents.png"),
    fullPage: true,
  });
});
