import { expect, test } from "@playwright/test";
import type { Locator, Page } from "@playwright/test";

// 80 px of the timeline are one second; every drag below moves whole frames at 30 fps.
async function drag(page: Page, target: Locator, dx: number) {
  const box = (await target.boundingBox())!;
  const x = box.x + box.width / 2;
  const y = box.y + box.height / 2;
  await page.mouse.move(x, y);
  await page.mouse.down();
  await page.mouse.move(x + dx / 2, y, { steps: 4 });
  await page.mouse.move(x + dx, y, { steps: 4 });
  await page.mouse.up();
}

test("inserir, mover, redimensionar e cortar um item na timeline, com desfazer e refazer", async ({
  page,
}, testInfo) => {
  const title = `Vídeo horizontal ${testInfo.project.name}`;
  await page.goto("/");
  await page.getByRole("button", { name: "Novo vídeo horizontal", exact: true }).click();
  const form = page.getByRole("form", { name: "Novo vídeo horizontal" });
  await form.getByLabel("Título").fill(title);
  await form.getByRole("button", { name: "Criar vídeo", exact: true }).click();
  await expect(page.getByRole("heading", { name: title })).toBeVisible();
  await expect(page.getByText("16:9 · 1920×1080 · 30 fps")).toBeVisible();
  await expect(page).toHaveURL(/#\/edicao\/[a-f0-9]{32}$/);

  const texts = page.getByRole("list", { name: "Faixa Textos" });
  await page.getByRole("button", { name: "Inserir item em Textos", exact: true }).click();
  await expect(texts.getByRole("button", { name: "Novo texto, 0,0 s a 2,0 s" })).toBeVisible();

  await drag(page, texts.getByRole("button", { name: /^Novo texto/ }), 40);
  await expect(texts.getByRole("button", { name: "Novo texto, 0,5 s a 2,5 s" })).toBeVisible();
  await expect(page.getByLabel("Início (s)")).toHaveValue("0.5");

  await drag(page, texts.locator(".timeline-handle.end"), -40);
  await expect(texts.getByRole("button", { name: "Novo texto, 0,5 s a 2,0 s" })).toBeVisible();

  const ruler = page.getByRole("slider", { name: "Cursor da timeline" });
  await ruler.click({ position: { x: 96, y: 12 } });
  await expect(ruler).toHaveAttribute("aria-valuenow", "1200");
  await page.getByRole("button", { name: "Cortar no cursor", exact: true }).click();
  await expect(texts.getByRole("button")).toHaveCount(2);
  await expect(texts.getByRole("button", { name: "Novo texto, 0,5 s a 1,2 s" })).toBeVisible();
  await expect(texts.getByRole("button", { name: "Novo texto, 1,2 s a 2,0 s" })).toBeVisible();

  await page.getByRole("button", { name: "Desfazer", exact: true }).click();
  await expect(texts.getByRole("button")).toHaveCount(1);
  await expect(texts.getByRole("button", { name: "Novo texto, 0,5 s a 2,0 s" })).toBeVisible();
  await page.getByRole("button", { name: "Refazer", exact: true }).click();
  await expect(texts.getByRole("button")).toHaveCount(2);

  // The document and its history come back from the service after a reload.
  await page.reload();
  await expect(texts.getByRole("button")).toHaveCount(2);
  const history = page.getByRole("list", { name: "Histórico de edição" });
  await expect(history.getByText("Refeito: Cortar item")).toBeVisible();
  await expect(history.getByText("Redimensionar item", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Desfazer", exact: true }).click();
  await expect(texts.getByRole("button")).toHaveCount(1);

  await page.getByLabel("Arquivo do recurso").setInputFiles({
    name: "fundo.png",
    mimeType: "image/png",
    buffer: Buffer.from(`imagem do teste ${testInfo.project.name}`),
  });
  await expect(page.getByRole("list", { name: "Recursos do projeto" }).getByText("fundo.png")).toBeVisible();
  await expect(page.getByText(/Apagar o histórico de edição: \d+ registros\. Libera 0 B/)).toBeVisible();
});
