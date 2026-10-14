import { expect, test } from "@playwright/test";

test("refresh e histórico preservam telas e aba do editor sem perder a proteção do rascunho", async ({
  page,
}) => {
  await page.goto("/");
  const navigation = page.getByRole("navigation", {
    name: "Navegação principal",
  });
  await navigation
    .getByRole("button", { name: "Configurações", exact: true })
    .click();
  await expect(page).toHaveURL(/#\/configuracoes\/agentes$/);
  await page.reload();
  await expect(page.getByRole("heading", { name: "Agentes" })).toBeVisible();
  await navigation
    .getByRole("button", { name: "Fila de produção", exact: true })
    .click();
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Fila de produção", exact: true }),
  ).toBeVisible();
  await page.goBack();
  await expect(page.getByRole("heading", { name: "Agentes" })).toBeVisible();
  await page.goForward();
  await expect(
    page.getByRole("heading", { name: "Fila de produção", exact: true }),
  ).toBeVisible();
  await navigation
    .getByRole("button", { name: "Produções", exact: true })
    .click();
  await page.getByRole("button", { name: "Novo Short", exact: true }).click();
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Da pauta ao Short." }),
  ).toBeVisible();
  await page.getByLabel("Abrir editor vazio").check();
  await page.getByLabel("Título de trabalho").fill("Navegação persistida");
  await page
    .getByRole("button", { name: "Criar produção", exact: true })
    .click();
  await page.getByRole("tab", { name: "Cenas", exact: true }).click();
  await expect(page).toHaveURL(/#\/producoes\/[a-f0-9]+\/scenes$/);
  await page.reload();
  await expect(
    page.getByRole("tab", { name: "Cenas", exact: true }),
  ).toHaveAttribute("aria-selected", "true");
  await page.getByLabel("Título em tela").fill("Rascunho protegido");
  await page.goBack(); // Back to the previous tab, with the same editor still mounted.
  await page.goForward();
  await expect(page.getByLabel("Título em tela")).toHaveValue(
    "Rascunho protegido",
  );
  const leaveDialog = page.waitForEvent("dialog");
  await page.evaluate(() => history.go(-2)); // Try to leave the project through history.
  await (await leaveDialog).dismiss();
  await expect(page).toHaveURL(/\/scenes$/);
  await expect(page.getByLabel("Título em tela")).toHaveValue(
    "Rascunho protegido",
  );
});
