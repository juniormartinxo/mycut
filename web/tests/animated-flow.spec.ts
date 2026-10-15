import { expect, test, type Page } from "@playwright/test";
import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { spawn } from "node:child_process";

const testPython = process.env.MYCUT_TEST_PYTHON || ["../.venv-app/bin/python", "../.venv-narration/bin/python"].map(p => resolve(p)).find(p => existsSync(p)) || "python3";
const NARRATION = "Seu pedido chega ao agente de IA, que chama uma ferramenta. A ferramenta devolve os dados e o agente monta a resposta para você.";

function referenceFlow() {
  const node = (id: string, label: string, icon: string | null, x: number, y: number, size = 22, shape = "circle", chart: unknown = null) =>
    ({ id, label, icon, shape, x, y, size, chart });
  return {
    nodes: [node("usuario", "Usuário", "user", 20, 14), node("agente", "Agente de IA", "bot", 50, 46, 24, "rounded"),
      node("ferramenta", "Ferramenta", "wrench", 80, 14),
      node("resposta", "Resposta", null, 50, 84, 56, "rounded", { kind: "bars", values: [12, 30, 54], labels: ["seg", "ter", "qua"], maximum: null, unit: "%" })],
    links: [{ source: "usuario", target: "agente" }, { source: "agente", target: "ferramenta" }, { source: "agente", target: "resposta" }],
    steps: [{ source: "usuario", target: "agente", kind: "request", anchor: "pedido" },
      { source: "agente", target: "ferramenta", kind: "request", anchor: "chama" },
      { source: "ferramenta", target: "agente", kind: "result", anchor: "devolve" },
      { source: "agente", target: "resposta", kind: "result", anchor: "resposta" }],
  };
}

async function flowProject(page: Page, title: string, flow: unknown) {
  const project = await (await page.request.post("/api/projects", { data: { title } })).json();
  const scene = project.scenes[0];
  scene.narration = NARRATION;
  scene.blocks[0].object = { id: "a".repeat(32), type: "title", text: "Como o agente responde", font_size: 64 };
  if (flow !== undefined) scene.blocks[1].object = { id: "c".repeat(32), type: "flow", font_size: 30, flow };
  const saved = await page.request.put(`/api/projects/${project.id}`, { data: { title, revision: project.revision, scenes: [scene] } });
  expect(saved.status()).toBe(200);
  return saved.json();
}

/** Pixels of the frame on screen versus a fresh server render of the saved scene at the same instant. */
async function sameAsServer(page: Page, projectId: string, elapsed: number) {
  return page.evaluate(async ({ projectId, elapsed }) => {
    const project = await (await fetch(`/api/projects/${projectId}`)).json();
    const fresh = await fetch("/api/scene-preview", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scene: project.scenes[0], project_id: projectId, accent: project.accent, visual_style: project.visual_style || null, elapsed }) });
    const shown = document.querySelector<HTMLImageElement>(".flow-frame");
    if (!shown) return -1;
    const pixels = async (blob: Blob) => {
      const bitmap = await createImageBitmap(blob);
      const canvas = new OffscreenCanvas(bitmap.width, bitmap.height);
      const context = canvas.getContext("2d")!;
      context.drawImage(bitmap, 0, 0);
      return context.getImageData(0, 0, bitmap.width, bitmap.height).data;
    };
    const [a, b] = await Promise.all([pixels(await (await fetch(shown.src)).blob()), pixels(await fresh.blob())]);
    if (a.length !== b.length) return -1;
    let different = 0;
    for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) different++;
    return different;
  }, { projectId, elapsed });
}

async function seek(page: Page, seconds: number) {
  await page.getByRole("slider", { name: "Tempo da cena", exact: true }).evaluate((input: HTMLInputElement, value) => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(input, String(value));
    input.dispatchEvent(new Event("input", { bubbles: true }));
  }, seconds);
}

test("Fluxo animado reproduz no editor com os quadros do servidor e persiste ao reabrir", async ({ page }, testInfo) => {
  const project = await flowProject(page, "Fluxo animado no editor", referenceFlow());
  await page.goto(`/#/producoes/${project.id}/scenes`);
  await page.getByRole("button", { name: "Editar cena", exact: true }).click();
  await page.getByRole("button", { name: "Selecionar bloco 2", exact: true }).click();
  await expect(page.getByRole("combobox", { name: "Objeto do bloco", exact: true })).toHaveValue("flow");
  await expect(page.getByText("4 nós · 3 conexões · 4 etapas", { exact: true })).toBeVisible();
  const steps = page.getByRole("list", { name: "Etapas do fluxo", exact: true }).getByRole("listitem");
  await expect(steps).toHaveCount(4);
  await expect(steps.first()).toContainText("Usuário → Agente de IA");
  await expect(steps.first()).toContainText("na fala “pedido”");
  await expect(steps.nth(2)).toContainText("resultado");
  const controls = page.getByRole("group", { name: "Prévia animada da cena", exact: true });
  await expect(controls.locator("output")).toHaveText("Estado final");
  await expect(controls).toContainText("Tempos estimados");
  await expect(page.locator(".flow-frame")).toHaveCount(0);

  await controls.getByRole("button", { name: "Reproduzir animação", exact: true }).click();
  await expect(page.locator(".flow-frame")).toBeVisible();
  await expect.poll(async () => Number((await controls.locator("output").textContent())!.split(" ")[0].replace(",", ".")), { timeout: 20_000 }).toBeGreaterThan(1);
  await controls.getByRole("button", { name: "Pausar animação", exact: true }).click();

  // Three instants: nodes entering, the tool working, the result chart built.
  const shots: string[] = [];
  for (const seconds of [1.2, 4.5, 8.5]) {
    await seek(page, seconds);
    await expect(controls.locator("output")).toContainText(`${seconds.toFixed(1).replace(".", ",")} s de`);
    await expect.poll(() => sameAsServer(page, project.id, seconds), { timeout: 20_000 }).toBe(0);
    shots.push(await page.locator(".flow-frame").evaluate((image: HTMLImageElement) => image.src));
  }
  expect(new Set(shots).size).toBe(3);
  await page.locator(".block-canvas").screenshot({ path: testInfo.outputPath(`fluxo-animado-${testInfo.project.name}.png`) });
  await controls.scrollIntoViewIfNeeded();
  await page.screenshot({ path: testInfo.outputPath(`fluxo-animado-editor-${testInfo.project.name}.png`) });
  await controls.getByRole("button", { name: "Mostrar estado final", exact: true }).click();
  await expect(page.locator(".flow-frame")).toHaveCount(0);

  const labels = page.getByLabel("Tamanho dos rótulos (px)", { exact: true });
  await labels.fill("28");
  await labels.press("Tab");
  await page.getByRole("button", { name: "Salvar", exact: true }).click();
  await expect(page.getByRole("dialog").getByText("Salvo", { exact: true })).toBeVisible();
  await page.reload();
  await page.getByRole("button", { name: "Editar cena", exact: true }).click();
  await page.getByRole("button", { name: "Selecionar bloco 2", exact: true }).click();
  await expect(page.getByText("4 nós · 3 conexões · 4 etapas", { exact: true })).toBeVisible();
  await expect(page.getByLabel("Tamanho dos rótulos (px)", { exact: true })).toHaveValue("28");
  const saved = await (await page.request.get(`/api/projects/${project.id}`)).json();
  expect(saved.scenes[0].blocks[1].object.font_size).toBe(28);
  expect(saved.scenes[0].blocks[1].object.flow.steps.map((s: { anchor: string }) => s.anchor)).toEqual(["pedido", "chama", "devolve", "resposta"]);
  expect(saved.scenes[0].blocks[0].object.flow).toBeUndefined();
});

test("quadro que falha mostra o erro sem repetir a requisição em laço", async ({ page }) => {
  const project = await flowProject(page, "Fluxo animado com falha", referenceFlow());
  let attempts = 0;
  await page.route("**/api/scene-preview", async route => {
    const body = route.request().postDataJSON();
    if (body.elapsed !== undefined && body.elapsed !== null && Math.abs(body.elapsed - 2) < .01) {
      attempts += 1;
      return route.fulfill({ status: 500, body: "falha simulada" });
    }
    return route.continue();
  });
  await page.goto(`/#/producoes/${project.id}/scenes`);
  await page.getByRole("button", { name: "Editar cena", exact: true }).click();
  const controls = page.getByRole("group", { name: "Prévia animada da cena", exact: true });
  await seek(page, 1.5);
  await controls.getByRole("button", { name: "Reproduzir animação", exact: true }).click();
  await expect(controls.getByRole("alert")).toContainText("Não foi possível gerar o quadro de 2,0 s.");
  await expect(controls.getByRole("button", { name: "Reproduzir animação", exact: true })).toBeVisible();
  await page.waitForTimeout(1500);
  expect(attempts).toBe(1);
  await controls.getByRole("button", { name: "Tentar novamente", exact: true }).click();
  await expect.poll(() => attempts).toBe(2);
  await page.waitForTimeout(1000);
  expect(attempts).toBe(2);
});

test("Fluxo animado sem montagem bloqueia a exportação e oferece o pedido ao agente", async ({ page }) => {
  const project = await flowProject(page, "Fluxo animado pendente", null);
  await page.goto(`/#/producoes/${project.id}/scenes`);
  await page.getByRole("button", { name: "Editar cena", exact: true }).click();
  await page.getByRole("button", { name: "Selecionar bloco 2", exact: true }).click();
  await expect(page.getByText("Este Fluxo animado ainda não foi montado.", { exact: true })).toBeVisible();
  await expect(page.getByRole("alert").filter({ hasText: "Peça ao agente para montar o Fluxo animado" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Pedir ao agente para montar", exact: true })).toBeVisible();
  await expect(page.getByRole("group", { name: "Prévia animada da cena", exact: true })).toHaveCount(0);
});

test("escolher Fluxo animado pede ao agente, que monta o fluxo para revisão e aceite", async ({ page }, testInfo) => {
  test.skip(!process.env.MYCUT_BLOCK_TEST_DATA, "Requer a instância isolada com worker e fixture de agente em /tmp.");
  const runner = spawn(testPython, [resolve("tests/fixtures/scene_agent_runner.py")], { env: process.env });
  try {
    await expect.poll(async () => (await (await page.request.get("/api/integrations")).json()).runner.online).toBe(true);
    const project = await flowProject(page, "Fluxo animado pelo agente", undefined);
    await page.goto(`/#/producoes/${project.id}/scenes`);
    await page.getByRole("button", { name: "Editar cena", exact: true }).click();
    await page.getByRole("button", { name: "Selecionar bloco 2", exact: true }).click();
    await page.getByRole("combobox", { name: "Objeto do bloco", exact: true }).selectOption("flow");
    await expect(page.getByRole("tab", { name: "Agente", exact: true })).toHaveAttribute("aria-selected", "true");
    await expect(page.getByText(/Monte um Fluxo animado para este objeto/)).toBeVisible();
    await page.getByRole("button", { name: "Revisar proposta", exact: true }).click({ timeout: 30_000 });
    await expect(page.locator(".proposal-pair img")).toHaveCount(2);
    expect((await (await page.request.get(`/api/projects/${project.id}`)).json()).scenes[0].blocks[1].object.flow).toBeUndefined();
    await page.getByRole("button", { name: "Aceitar proposta", exact: true }).click();
    await expect(page.getByText("Proposta aceita", { exact: true })).toBeVisible();
    await page.getByRole("tab", { name: "Objeto", exact: true }).click();
    await expect(page.getByText("4 nós · 3 conexões · 4 etapas", { exact: true })).toBeVisible();
    await expect(page.getByRole("list", { name: "Etapas do fluxo", exact: true })).toContainText("na fala “devolve”");
    await page.getByRole("button", { name: "Reproduzir animação", exact: true }).click();
    await expect(page.locator(".flow-frame")).toBeVisible();
    await page.locator(".block-canvas").screenshot({ path: testInfo.outputPath(`fluxo-animado-agente-${testInfo.project.name}.png`) });
    const saved = await (await page.request.get(`/api/projects/${project.id}`)).json();
    expect(saved.scenes[0].blocks[1].object.flow.nodes.map((n: { label: string }) => n.label)).toEqual(["Usuário", "Agente de IA", "Ferramenta", "Resposta"]);
  } finally {
    runner.kill("SIGTERM");
    await new Promise<void>(done => { runner.once("exit", () => done()); setTimeout(done, 3000); });
  }
});
