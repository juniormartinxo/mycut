import { expect, test } from "@playwright/test";

test("criar e editar um canal e escolhê-lo ao criar uma produção", async ({
  page,
}, testInfo) => {
  const name = `Histórias dark ${testInfo.project.name}`;
  const renamed = `Contos dark ${testInfo.project.name}`;
  await page.goto("/#/configuracoes/canais");
  const list = page.getByRole("list", { name: "Canais" });
  await expect(list.getByText("Meu canal", { exact: true })).toBeVisible();
  await expect(list.getByText("Padrão", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Novo canal", exact: true }).click();
  const form = page.getByRole("form", { name: "Novo canal" });
  await form.getByLabel("Nome do canal").fill(name);
  await form.getByLabel("Marca do canal").fill("@historias");
  await form.getByRole("button", { name: "Criar canal", exact: true }).click();
  await expect(page.getByRole("status").getByText(`Canal ${name} criado.`)).toBeVisible();
  await expect(list.getByText(name, { exact: true })).toBeVisible();

  await list.getByRole("button", { name: `Editar ${name}`, exact: true }).click();
  const edit = page.getByRole("form", { name: "Editar canal" });
  await expect(edit.getByLabel("Marca do canal")).toHaveValue("@historias");
  await edit.getByLabel("Nome do canal").fill(renamed);
  await edit.getByRole("button", { name: "Salvar canal", exact: true }).click();
  await expect(list.getByText(renamed, { exact: true })).toBeVisible();
  await page.reload();
  await expect(list.getByText(renamed, { exact: true })).toBeVisible();
  await expect(list.getByText(name, { exact: true })).toHaveCount(0);

  await page.goto("/#/novo");
  const channel = page.getByRole("combobox", { name: "Canal", exact: true });
  await expect(channel).toHaveValue(/.+/);
  await expect(page.getByLabel("Nome do canal no vídeo")).toHaveValue("MYCUT");
  await channel.selectOption({ label: renamed });
  await expect(page.getByLabel("Nome do canal no vídeo")).toHaveValue("@historias");
  await page.getByLabel("Abrir editor vazio").check();
  await page.getByLabel("Título de trabalho").fill(`Produção do canal ${testInfo.project.name}`);
  await page.getByRole("button", { name: "Criar produção", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: `Produção do canal ${testInfo.project.name}` }),
  ).toBeVisible();
  await expect(page.locator(".topbar")).toContainText(renamed);
});
