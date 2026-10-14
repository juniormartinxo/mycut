import { expect, test } from "@playwright/test";

test("criar, editar sem perder texto, produzir e baixar uma versão", async ({
  page,
}, testInfo) => {
  const title = `Teste de estúdio ${testInfo.project.name}`;
  await page.goto("/");
  await page.getByRole("button", { name: "Novo Short", exact: true }).click();
  await page.getByLabel("Abrir editor vazio").check();
  await page.getByLabel("Título de trabalho").fill(title);
  await page
    .getByRole("button", { name: "Criar produção", exact: true })
    .click();
  await expect(page.getByRole("heading", { name: title })).toBeVisible();

  await page.getByRole("tab", { name: "Roteiro", exact: true }).click();
  for (let i = 1; i <= 3; i++) {
    await page
      .getByLabel(`Narração da cena ${i}`, { exact: true })
      .fill(`A ideia ${i} aparece no vídeo.`);
  }
  const navigation = page.getByRole("navigation", {
    name: "Navegação principal",
  });
  for (const name of ["Produções", "Fila de produção", "Conexões"]) {
    page.once("dialog", (dialog) => dialog.dismiss());
    await navigation.getByRole("button", { name, exact: true }).click();
    await expect(
      page.getByLabel("Narração da cena 1", { exact: true }),
    ).toHaveValue("A ideia 1 aparece no vídeo.");
  }
  await page.getByRole("tab", { name: "Cenas", exact: true }).click();
  await page.getByLabel("Formato visual").selectOption("comparison");
  await page
    .getByLabel("Opção 1 da comparação")
    .fill("Computador\nSessão local");
  await page
    .getByLabel("Opção 2 da comparação")
    .fill("Nuvem\nSessão independente");
  await page
    .getByRole("button", { name: "Salvar alterações", exact: true })
    .click();
  await expect(
    page.getByText("Alterações salvas.", { exact: true }),
  ).toBeVisible();
  await page.reload();
  await page.getByRole("tab", { name: "Cenas", exact: true }).click();
  await expect(page.getByLabel("Opção 2 da comparação")).toHaveValue(
    "Nuvem\nSessão independente",
  );

  await page
    .getByRole("button", { name: "Renderizar cenas atuais", exact: true })
    .click();
  await expect(
    page.getByRole("link", { name: "MP4", exact: true }),
  ).toBeVisible({ timeout: 90_000 });
  const download = page.waitForEvent("download");
  await page
    .getByRole("link", { name: "Pacote completo", exact: true })
    .click();
  expect((await download).suggestedFilename()).toMatch(/^mycut-.*\.zip$/);
  await expect(
    page.getByText("Sem narração · tempos estimados", { exact: true }),
  ).toBeVisible();

  // Another tab can remove scenes while this editor is clean and showing the last one.
  await page
    .getByRole("button", { name: "Editar cena 3", exact: true })
    .click();
  const projectId = new URL(page.url()).hash.split("/")[2];
  const project = await (
    await page.request.get(`/api/projects/${projectId}`)
  ).json();
  const { description, tags, sources, accent, revision } = project;
  const update = await page.request.put(`/api/projects/${projectId}`, {
    data: {
      title,
      description,
      tags,
      sources,
      accent,
      revision,
      scenes: project.scenes.slice(0, 1),
    },
  });
  expect(update.status()).toBe(200);
  await expect(
    page.getByRole("button", { name: "Editar cena 3", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Mover cena para cima", exact: true }),
  ).toBeDisabled();
  await page.getByLabel("Título em tela").fill("Cena atualizada");
  await page
    .getByRole("button", { name: "Salvar alterações", exact: true })
    .click();
  await expect(
    page.getByText("Alterações salvas.", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "MP4", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("Versão anterior. Gere novamente após salvar.", {
      exact: true,
    }),
  ).toBeVisible();

  await expect
    .poll(() =>
      page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    )
    .toBe(true);
  await page.screenshot({
    path: testInfo.outputPath("editor.png"),
    fullPage: true,
  });
  await navigation
    .getByRole("button", { name: "Produções", exact: true })
    .click();
  await page.screenshot({
    path: testInfo.outputPath("producoes.png"),
    fullPage: true,
  });
});

test("conexões e entrada por pauta são o caminho principal", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Novo Short", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Da pauta ao Short." }),
  ).toBeVisible();
  await expect(page.getByLabel("Short completo")).toBeChecked();
  await expect(
    page.getByText("Roteiro do Claude Code", { exact: true }),
  ).toHaveCount(0);
  await page.getByLabel("Pauta ou link").fill("https://example.com/news");
  await expect(
    page.getByRole("button", { name: "Produzir com agentes", exact: true }),
  ).toBeDisabled();
  await page
    .getByRole("button", { name: "Configurar conexões", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Conexões e agentes" }),
  ).toBeVisible();
  await expect(
    page.getByText("bash scripts/agents.sh", { exact: true }),
  ).toBeVisible();
  await expect(page.getByLabel("Chave de API da ElevenLabs")).toHaveAttribute(
    "type",
    "password",
  );
  await expect
    .poll(() =>
      page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    )
    .toBe(true);
});

test("pauta sobrevive à ida para configurar conexões", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Novo Short", exact: true }).click();
  await page
    .getByLabel("Pauta ou link")
    .fill("https://example.com/minha-pauta");
  await page
    .getByRole("button", { name: "Configurar conexões", exact: true })
    .click();
  await page
    .getByRole("navigation")
    .getByRole("button", { name: "Produções", exact: true })
    .click();
  await page.getByRole("button", { name: "Novo Short", exact: true }).click();
  await expect(page.getByLabel("Pauta ou link")).toHaveValue(
    "https://example.com/minha-pauta",
  );
});
