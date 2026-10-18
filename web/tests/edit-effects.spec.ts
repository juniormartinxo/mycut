import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

async function goTo(page: Page, seconds: string) {
  const instant = page.getByLabel("Instante (s)");
  await instant.fill(seconds);
  await instant.press("Enter");
}

test("editar os pontos no tempo de um item, com desfazer, e ver a prévia acompanhar", async ({ page }, testInfo) => {
  const title = `Pontos no tempo ${testInfo.project.name}`;
  await page.goto("/");
  await page.getByRole("button", { name: "Novo vídeo horizontal", exact: true }).click();
  const form = page.getByRole("form", { name: "Novo vídeo horizontal" });
  await form.getByLabel("Título").fill(title);
  await form.getByRole("button", { name: "Criar vídeo", exact: true }).click();
  await expect(page.getByRole("heading", { name: title })).toBeVisible();
  const preview = page.getByRole("img", { name: "Quadro da prévia" });
  await expect(preview).toHaveAttribute("data-ms", "0");

  await page.getByRole("button", { name: "Inserir item em Textos", exact: true }).click();
  const texts = page.getByRole("list", { name: "Faixa Textos" });
  await expect(texts.getByRole("button", { name: "Novo texto, 0,0 s a 2,0 s" })).toBeVisible();
  // The new text is drawn by the preview, which only shows a frame once it is complete.
  await expect(preview.getByText("Novo texto")).toBeVisible();

  await page.getByLabel("Propriedade").selectOption({ label: "Opacidade" });
  await expect(page.getByText("Opacidade fica em 1 durante todo o item.")).toBeVisible();
  await page.getByRole("button", { name: "Adicionar ponto no cursor", exact: true }).click();
  const points = page.getByRole("list", { name: "Pontos no tempo de Opacidade" });
  await expect(points.getByRole("listitem")).toHaveCount(1);
  await expect(page.getByLabel("Valor do ponto 1")).toHaveValue("1");
  await page.getByLabel("Valor do ponto 1").fill("0");
  await page.getByLabel("Valor do ponto 1").press("Enter");
  await expect(page.getByLabel("Valor do ponto 1")).toHaveValue("0");

  await goTo(page, "1");
  await expect(preview).toHaveAttribute("data-ms", "1000");
  // At 1 s the only point still holds: the text is invisible.
  await expect(preview.locator(".stage-layer.text")).toHaveCSS("opacity", "0");
  await page.getByRole("button", { name: "Adicionar ponto no cursor", exact: true }).click();
  await expect(points.getByRole("listitem")).toHaveCount(2);
  await page.getByLabel("Valor do ponto 2").fill("1");
  await page.getByLabel("Valor do ponto 2").press("Enter");
  await expect(page.getByLabel("Valor do ponto 2")).toHaveValue("1");
  await expect(preview.locator(".stage-layer.text")).toHaveCSS("opacity", "1");
  // The points stay editable: the second one moves to 1.5 s and its curve changes.
  await page.getByLabel("Instante do ponto 2 (s)").fill("1.5");
  await page.getByLabel("Instante do ponto 2 (s)").press("Enter");
  await expect(page.getByLabel("Instante do ponto 2 (s)")).toHaveValue("1.5");
  await expect(preview.locator(".stage-layer.text")).toHaveCSS("opacity", "0.666667");
  await page.getByLabel("Curva do ponto 2").selectOption({ label: "Degrau" });
  await expect(page.getByLabel("Curva do ponto 2")).toHaveValue("hold");
  await expect(texts.locator(".timeline-keyframe")).toHaveCount(2);

  await page.getByRole("button", { name: "Desfazer", exact: true }).click();
  await expect(page.getByLabel("Curva do ponto 2")).toHaveValue("linear");
  await page.getByRole("button", { name: "Desfazer", exact: true }).click();
  await expect(page.getByLabel("Instante do ponto 2 (s)")).toHaveValue("1");
  await page.getByRole("button", { name: "Refazer", exact: true }).click();
  await expect(page.getByLabel("Instante do ponto 2 (s)")).toHaveValue("1.5");

  await page.getByRole("button", { name: "Remover ponto 1", exact: true }).click();
  await expect(points.getByRole("listitem")).toHaveCount(1);
  await expect(page.getByLabel("Instante do ponto 1 (s)")).toHaveValue("1.5");
  await page.reload();
  await expect(page.getByRole("heading", { name: title })).toBeVisible();
  await texts.getByRole("button", { name: /^Novo texto/ }).click();
  await expect(page.getByLabel("Propriedade")).toHaveValue("opacity");
  await expect(page.getByLabel("Instante do ponto 1 (s)")).toHaveValue("1.5");
  await expect(page.getByRole("list", { name: "Histórico de edição" }).getByText("Alterar pontos no tempo").first()).toBeVisible();
});
