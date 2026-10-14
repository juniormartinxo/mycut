import { expect, test } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

let fixtureDirectory: string;
let clip: string;
test.beforeAll(() => {
  fixtureDirectory = mkdtempSync(join(tmpdir(), "mycut-ending-browser-"));
  clip = join(fixtureDirectory, "Convite final.mp4");
  execFileSync("ffmpeg", ["-v", "error", "-f", "lavfi", "-i", "color=red:s=108x192:r=24", "-f", "lavfi", "-i", "sine=frequency=880:sample_rate=48000", "-t", "0.8", "-c:v", "libx264", "-threads", "1", "-pix_fmt", "yuv420p", "-c:a", "aac", clip]);
});
test.afterAll(() => rmSync(fixtureDirectory, { recursive: true, force: true }));

test("importar, incluir, salvar, renderizar e retirar o encerramento", async ({ page }, testInfo) => {
  const created = await page.request.post("/api/projects", { data: { title: `Encerramento ${testInfo.project.name}` } });
  const project = await created.json();
  const updated = await page.request.put(`/api/projects/${project.id}`, { data: {
    title: project.title, revision: project.revision,
    scenes: [{ title: "Uma ideia", narration: "Uma ideia clara.", layout: "statement", items: ["Teste"] }],
  } });
  expect(updated.ok()).toBeTruthy();
  await page.goto(`/#/producoes/${project.id}/ending`);
  await expect(page.getByRole("tab", { name: "Encerramento", exact: true })).toHaveAttribute("aria-selected", "true");
  const toggle = page.getByLabel("Incluir no final deste Short", { exact: true });
  await expect(toggle).not.toBeChecked();
  await expect(page.getByText("Carregando vídeos de encerramento…")).toHaveCount(0);
  await page.getByLabel("Importar vídeo de encerramento", { exact: true }).setInputFiles(clip);
  await expect(page.getByText("Vídeo importado. Ele também fica disponível nas outras produções.")).toBeVisible();
  await expect(toggle).not.toBeChecked();
  await expect(page.getByLabel("Prévia do encerramento", { exact: true })).toHaveAttribute("src", /\/api\/endings\//);
  await toggle.check();
  await page.getByRole("button", { name: "Salvar alterações", exact: true }).click();
  await expect(page.getByText("Alterações salvas.", { exact: true })).toBeVisible();
  await page.reload();
  await expect(toggle).toBeChecked();
  const saved = await (await page.request.get(`/api/projects/${project.id}`)).json();
  expect(saved.ending_id).toMatch(/^[a-f0-9]{32}$/);
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.getByRole("button", { name: "Renderizar cenas atuais", exact: true }).click();
  await expect(page.getByRole("link", { name: "MP4", exact: true })).toBeVisible({ timeout: 90_000 });
  const rendered = await (await page.request.get(`/api/projects/${project.id}`)).json();
  const version = rendered.jobs.find((job: { output: unknown }) => job.output);
  expect(version.output.ending.id).toBe(saved.ending_id);
  expect(version.output.has_audio).toBe(true);
  expect(version.output.has_narration).toBe(false);
  await expect(page.getByText("Cenas sem narração · encerramento com áudio", { exact: true })).toBeVisible();
  const response = await page.request.get(`/api/jobs/${version.id}/files/short.mp4`, { headers: { Range: "bytes=0-1023" } });
  expect(response.status()).toBe(206);
  await toggle.uncheck();
  await page.getByRole("button", { name: "Salvar alterações", exact: true }).click();
  await expect(page.getByText("Alterações salvas.", { exact: true })).toBeVisible();
  await page.reload();
  await expect(toggle).not.toBeChecked();
  expect((await (await page.request.get(`/api/projects/${project.id}`)).json()).ending_id).toBeNull();
  await page.getByRole("button", { name: "Renderizar cenas atuais", exact: true }).click();
  await expect.poll(async () => {
    const latest = await (await page.request.get(`/api/projects/${project.id}`)).json();
    return latest.jobs[0]?.state;
  }, { timeout: 90_000 }).toBe("succeeded");
  const without = await (await page.request.get(`/api/projects/${project.id}`)).json();
  expect(without.jobs[0].output.ending).toBeNull();
  expect(without.jobs[0].output.duration).toBeLessThan(version.output.duration);
});

test("biblioteca vazia e falha de carregamento permitem recuperação", async ({ page }) => {
  const created = await page.request.post("/api/projects", { data: { title: "Biblioteca de encerramentos" } });
  const project = await created.json();
  let fail = true;
  await page.route("**/api/endings", (route) => route.fulfill(route.request().method() === "POST"
    ? { status: 422, json: { detail: "Vídeo inválido neste teste." } }
    : fail
      ? { status: 503, json: { detail: "Biblioteca indisponível neste teste." } }
      : { json: [] }));
  await page.goto(`/#/producoes/${project.id}/ending`);
  await expect(page.getByRole("alert")).toContainText("Biblioteca indisponível neste teste.");
  fail = false;
  await page.getByRole("button", { name: "Tentar novamente", exact: true }).click();
  await expect(page.getByRole("alert")).toHaveCount(0);
  await expect(page.getByText("Importe seu primeiro encerramento para assistir e escolher em quais Shorts ele aparece.")).toBeVisible();
  await expect(page.getByLabel("Incluir no final deste Short", { exact: true })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Importar vídeo", exact: true })).toBeEnabled();
  await page.getByLabel("Importar vídeo de encerramento", { exact: true }).setInputFiles(clip);
  await expect(page.getByRole("alert")).toContainText("Vídeo inválido neste teste.");
  const chooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: "Escolher outro vídeo", exact: true }).click();
  expect((await chooser).isMultiple()).toBe(false);
});
