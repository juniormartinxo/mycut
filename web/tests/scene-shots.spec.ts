import { expect, test } from "@playwright/test";
import { existsSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { resolve } from "node:path";
import { execFileSync } from "node:child_process";

const testPython = process.env.MYCUT_TEST_PYTHON || ["../.venv-app/bin/python", "../.venv-narration/bin/python"].map(p => resolve(p)).find(p => existsSync(p)) || "python3";

test("planos com fundo, revelação e transição são criados, salvos e reordenados no editor", async ({ page }, testInfo) => {
  const project = await (await page.request.post("/api/projects", { data: { title: "Planos no editor" } })).json();
  const scene = { ...project.scenes[0], narration: "Primeiro o tom da história. Depois a ficha da personagem com números exatos." };
  const fields = ["title", "description", "tags", "sources", "brief", "accent", "accent_locked", "visual_style", "ending_id", "revision"];
  const body = { ...Object.fromEntries(fields.map(key => [key, project[key]])), scenes: [scene] };
  expect((await page.request.put(`/api/projects/${project.id}`, { data: body })).status()).toBe(200);
  await page.goto(`/#/producoes/${project.id}/scenes`);
  await page.getByRole("button", { name: "Editar cena", exact: true }).click();
  const dialog = page.getByRole("dialog");
  const strip = dialog.getByRole("navigation", { name: "Planos da cena" });
  await expect(strip.getByRole("button", { name: /^Plano 1/ })).toHaveAttribute("aria-current", "step");

  await dialog.getByRole("combobox", { name: "Objeto do bloco", exact: true }).selectOption("title");
  await dialog.getByLabel("Texto do título", { exact: true }).fill("ETAPA 1: TOM");

  await strip.getByRole("button", { name: "Plano", exact: true }).click();
  await expect(strip.getByRole("button", { name: /^Plano 2/ })).toHaveAttribute("aria-current", "step");
  await expect(dialog.getByRole("tab", { name: "Plano", exact: true })).toHaveAttribute("aria-selected", "true");
  await dialog.getByLabel("Começa na fala", { exact: true }).fill("ficha");
  await dialog.getByRole("combobox", { name: "Transição de entrada", exact: true }).selectOption("fade");
  await dialog.getByRole("combobox", { name: "Fundo", exact: true }).selectOption("gradient");
  await expect(dialog.getByLabel("Cor final", { exact: true })).toBeVisible();
  await dialog.getByLabel("Mostrar a marca do canal", { exact: true }).uncheck();
  await expect(strip.getByRole("button", { name: /^Plano 2/ })).toHaveAccessibleName(/^Plano 2, começa em \d+,\d s$/);

  await dialog.getByRole("tab", { name: "Objeto", exact: true }).click();
  await dialog.getByRole("button", { name: "Selecionar bloco 2", exact: true }).click();
  await dialog.getByRole("combobox", { name: "Objeto do bloco", exact: true }).selectOption("paragraph");
  await dialog.getByLabel("Texto do parágrafo", { exact: true }).fill("Idade: 38 anos\nAltura: 172 cm");
  await dialog.getByRole("combobox", { name: "Entrada do texto", exact: true }).selectOption("lines");
  await expect(dialog.getByRole("group", { name: "Prévia animada da cena" })).toBeVisible();
  await dialog.screenshot({ path: testInfo.outputPath("planos.png") });

  await dialog.getByRole("button", { name: "Salvar", exact: true }).click();
  await expect(dialog.getByText("Salvo", { exact: true })).toBeVisible();
  let saved = (await (await page.request.get(`/api/projects/${project.id}`)).json()).scenes[0];
  expect(saved.blocks[0].object).toMatchObject({ type: "title", text: "ETAPA 1: TOM" });
  expect(saved.shots).toHaveLength(1);
  expect(saved.shots[0]).toMatchObject({ anchor: "ficha", transition: "fade", brand: false, background: { kind: "gradient" } });
  expect(saved.shots[0].blocks[1].object).toMatchObject({ type: "paragraph", reveal: "lines" });

  // Moving the second plano first keeps the scene's identity on the new first plano.
  await dialog.getByRole("tab", { name: "Plano", exact: true }).click();
  await dialog.getByRole("button", { name: "Mover plano para antes", exact: true }).click();
  await expect(strip.getByRole("button", { name: /^Plano 1/ })).toHaveAttribute("aria-current", "step");
  await dialog.getByRole("button", { name: "Salvar", exact: true }).click();
  await expect(dialog.getByText("Salvo", { exact: true })).toBeVisible();
  saved = (await (await page.request.get(`/api/projects/${project.id}`)).json()).scenes[0];
  expect(saved.id).toBe(scene.id);
  expect(saved.background).toMatchObject({ kind: "gradient" });
  expect(saved.brand).toBe(false);
  expect(saved.shots[0].blocks[0].object).toMatchObject({ text: "ETAPA 1: TOM" });
  // Start and transition stay with the position: moving back restores the plano exactly.
  expect(saved.shots[0]).toMatchObject({ anchor: "ficha", transition: "fade" });
  const shotId = saved.shots[0].id;
  await dialog.getByRole("button", { name: "Mover plano para depois", exact: true }).click();
  await dialog.getByRole("button", { name: "Salvar", exact: true }).click();
  await expect(dialog.getByText("Salvo", { exact: true })).toBeVisible();
  saved = (await (await page.request.get(`/api/projects/${project.id}`)).json()).scenes[0];
  expect(saved.blocks[0].object).toMatchObject({ text: "ETAPA 1: TOM" });
  expect(saved.shots[0]).toMatchObject({ id: shotId, anchor: "ficha", transition: "fade", brand: false, background: { kind: "gradient" } });
  await expect(dialog.getByLabel("Começa na fala", { exact: true })).toHaveValue("ficha");

  await strip.getByRole("button", { name: /^Plano 2/ }).click();
  await expect(strip.getByRole("button", { name: /^Plano 2/ })).toHaveAttribute("aria-current", "step");
  await dialog.getByRole("button", { name: "Excluir plano", exact: true }).click();
  await expect(strip.getByRole("button", { name: /^Plano 2/ })).toHaveCount(0);
  await dialog.getByRole("button", { name: "Desfazer", exact: true }).click();
  await expect(strip.getByRole("button", { name: /^Plano 2/ })).toBeVisible();
});

test("imagem importada vira o fundo em tela cheia do plano, com movimento de câmera", async ({ page }, testInfo) => {
  const directory = mkdtempSync(resolve(tmpdir(), "mycut-shot-"));
  try {
    const picture = resolve(directory, "corredor.png");
    execFileSync(testPython, ["-c", "from PIL import Image,ImageDraw; import sys; im=Image.new('RGB',(900,1600),'#0e3b43'); ImageDraw.Draw(im).rectangle((300,500,600,1100),fill='#d98a1c'); im.save(sys.argv[1])", picture]);
    const project = await (await page.request.post("/api/projects", { data: { title: "Fundo em tela cheia" } })).json();
    await page.goto(`/#/producoes/${project.id}/scenes`);
    await page.getByRole("button", { name: "Editar cena", exact: true }).click();
    const dialog = page.getByRole("dialog");
    await dialog.getByRole("tab", { name: "Plano", exact: true }).click();
    await dialog.getByRole("combobox", { name: "Fundo", exact: true }).selectOption("image");
    await expect(dialog.getByRole("alert").filter({ hasText: "selecione o arquivo do fundo" })).toBeVisible();
    const [chooser] = await Promise.all([page.waitForEvent("filechooser"), dialog.getByRole("button", { name: "Importar imagem", exact: true }).click()]);
    await chooser.setFiles(picture);
    await expect(dialog.getByRole("combobox", { name: "Arquivo da biblioteca", exact: true })).not.toHaveValue("");
    await dialog.getByRole("combobox", { name: "Movimento de câmera", exact: true }).selectOption("zoom_in");
    await dialog.getByLabel("Escurecer o fundo", { exact: true }).fill("30");
    await expect(dialog.getByRole("alert").filter({ hasText: "selecione o arquivo do fundo" })).toHaveCount(0);
    await expect(dialog.getByRole("group", { name: "Prévia animada da cena" })).toBeVisible();
    await dialog.screenshot({ path: testInfo.outputPath("fundo.png") });
    await dialog.getByRole("button", { name: "Salvar", exact: true }).click();
    await expect(dialog.getByText("Salvo", { exact: true })).toBeVisible();
    const saved = await (await page.request.get(`/api/projects/${project.id}`)).json();
    expect(saved.scenes[0].background).toMatchObject({ kind: "image", asset_id: saved.images[0].id, motion: "zoom_in", dim: 30 });
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});
