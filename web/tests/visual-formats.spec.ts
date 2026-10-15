import { test, expect, type Page } from "@playwright/test";
import { builtApp } from "./fixtures/builtApp";
import type { Project } from "../src/types";

const id = "abcdef1234567890abcdef1234567890";
const imageId = "1234567890abcdef1234567890abcdef";
// Local, synthetic red PNG; never an external image or provider request.
const redPng = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADUlEQVQIHWP4z8AAAAMBAQDJ/pLvAAAAAElFTkSuQmCC",
  "base64",
);
function project(): Project {
  return {
    id,
    title: "Tarefas na nuvem",
    brief: "Explique tarefas na nuvem",
    description: "",
    tags: "",
    sources: "",
    accent: "#B9F078",
    accent_locked: true,
    visual_style: {
      format_id: "radar",
      font: "sans",
      background: "#121C24",
      text_color: "#F0F6F9",
      media_mode: "mixed",
      image_source: "both",
    },
    images: [],
    revision: 1,
    created_at: 0,
    updated_at: 0,
    jobs: [],
    audio_matches_script: true,
    usage_total: {
      input: 0,
      cache_read: 0,
      cache_write: 0,
      output: 0,
      reasoning: 0,
      web_searches: 0,
      credits: 0,
      usd: 0,
      unpriced: 0,
    },
    scenes: [
      {
        title: "Da ideia à ação",
        narration: "Você define a tarefa e revisa o resultado.",
        layout: "flow",
        items: ["Seu pedido", "Execução", "Revisão"],
      },
    ],
  };
}
async function agents(page: Page) {
  await page.route("**/api/integrations", (route) =>
    route.fulfill({
      json: {
        agents: Object.fromEntries(
          ["research", "writer", "director", "reviewer"].map((role) => [
            role,
            { provider: "codex", model: "" },
          ]),
        ),
        runner: { online: true, protocol: 3, providers: { codex: true } },
        elevenlabs: { connected: false, voice_id: "" },
      },
    }),
  );
}
async function settled(page: Page) {
  await expect(page.locator(".rendered-scene[aria-busy=true]")).toHaveCount(0);
  await expect
    .poll(() =>
      page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    )
    .toBe(true);
  await expect(
    page.getByText("Prévia indisponível.", { exact: false }),
  ).toHaveCount(0);
}

test("escolher formato, personalizar tudo e manter após salvar e atualizar", async ({
  page,
}, info) => {
  await builtApp(page);
  await agents(page);
  let saved: Project | null = null;
  await page.route("**/api/projects", (route) => {
    if (route.request().method() === "POST") {
      saved = { ...project(), ...route.request().postDataJSON() };
      return route.fulfill({ status: 201, json: saved });
    }
    return route.fulfill({ json: saved ? [saved] : [] });
  });
  await page.route(`**/api/projects/${id}`, (route) =>
    route.fulfill({ json: saved }),
  );
  await page.goto("/#/novo");
  await page
    .getByLabel("Pauta ou link")
    .fill("Como tarefas continuam na nuvem");
  await page.getByLabel("Roteiro e cenas primeiro").check();
  await page.getByRole("radio", { name: "Radar tech", exact: true }).check();
  await expect(page.getByLabel("Cor de fundo", { exact: true })).toHaveValue(
    "#121c24",
  );
  await settled(page);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({
    path: info.outputPath("formats-gallery.png"),
    fullPage: true,
  });
  await page.getByLabel("Fonte dos layouts anteriores").selectOption("mono");
  await page.getByLabel("Nome do canal no vídeo").fill("@JuniorIA");
  await page.getByLabel("Cor de fundo", { exact: true }).fill("#142138");
  await page.getByLabel("Cor do texto", { exact: true }).fill("#f7efcf");
  await page.getByLabel("Cor de destaque", { exact: true }).fill("#ffb75e");
  await page
    .getByRole("combobox", { name: "Conteúdo visual", exact: true })
    .selectOption("mixed");
  await page.getByLabel("Origem das imagens").selectOption("both");
  await page
    .getByRole("navigation", { name: "Navegação principal" })
    .getByRole("button", { name: "Fila de produção" })
    .click();
  await page.goBack();
  await expect(
    page.getByRole("radio", { name: "Radar tech", exact: true }),
  ).toBeChecked();
  await expect(page.getByLabel("Fonte dos layouts anteriores")).toHaveValue("mono");
  await expect(page.getByLabel("Nome do canal no vídeo")).toHaveValue("@JuniorIA");
  await settled(page);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({
    path: info.outputPath("custom-format.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "Criar roteiro com agentes" }).click();
  await expect(page).toHaveURL(new RegExp(id));
  expect(saved).toMatchObject({
    accent: "#ffb75e",
    visual_style: {
      format_id: "radar",
      channel_name: "@JuniorIA",
      font: "mono",
      background: "#142138",
      text_color: "#f7efcf",
      media_mode: "mixed",
      image_source: "both",
    },
  });
  await page.reload();
  await expect(page.getByLabel("Nome do canal no vídeo")).toHaveValue("@JuniorIA");
  await expect(page.getByLabel("Fonte dos layouts anteriores")).toHaveValue("mono");
  await expect(page.getByLabel("Cor de fundo", { exact: true })).toHaveValue(
    "#142138",
  );
  await page
    .getByRole("button", { name: "Restaurar aparência do formato" })
    .click();
  await expect(page.getByLabel("Cor de fundo", { exact: true })).toHaveValue(
    "#121c24",
  );
  await expect(
    page.getByRole("combobox", { name: "Conteúdo visual", exact: true }),
  ).toHaveValue("mixed");
  await expect(page.getByLabel("Nome do canal no vídeo")).toHaveValue("@JuniorIA");
  await page.getByRole("radio", { name: "Impacto", exact: true }).check();
  await expect(page.getByLabel("Nome do canal no vídeo")).toHaveValue("@JuniorIA");
  await page.getByLabel("Nome do canal no vídeo").fill("");
  await settled(page);
  await expect(page.getByLabel("Nome do canal no vídeo")).toHaveValue("");
});

test("imagem por cena, enquadramento e retorno para animação", async ({
  page,
}, info) => {
  await builtApp(page, redPng);
  await agents(page);
  let current = project();
  const writes: Record<string, unknown>[] = [];
  await page.route("**/api/projects", (route) =>
    route.fulfill({ json: [current] }),
  );
  await page.route(`**/api/projects/${id}`, (route) => {
    if (route.request().method() === "PUT") {
      const data = route.request().postDataJSON();
      writes.push(data);
      current = { ...current, ...data, revision: current.revision + 1 };
    }
    return route.fulfill({ json: current });
  });
  await page.route(`**/api/projects/${id}/images?*`, (route) => {
    expect(route.request().method()).toBe("POST");
    current = {
      ...current,
      revision: current.revision + 1,
      images: [
        {
          id: imageId,
          name: "Exemplo enviado.png",
          url: "/test-image.png",
          width: 1,
          height: 1,
          source_url: "",
          page_url: "",
        },
      ],
    };
    return route.fulfill({ json: current });
  });
  await page.goto(`/#/producoes/${id}/scenes`);
  await page.getByLabel("Adicionar imagem à cena").setInputFiles({
    name: "Exemplo enviado.png",
    mimeType: "image/png",
    buffer: redPng,
  });
  await expect(page.getByLabel("Conteúdo desta cena")).toHaveValue(imageId);
  await page.getByLabel("Enquadramento da imagem").selectOption("cover");
  await settled(page);
  await page
    .getByRole("button", { name: "Salvar alterações", exact: true })
    .click();
  expect(writes.at(-1)).toMatchObject({
    scenes: [{ image_id: imageId, image_fit: "cover" }],
  });
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({
    path: info.outputPath("scene-with-image.png"),
    fullPage: true,
  });
  await page.reload();
  await expect(page.getByLabel("Conteúdo desta cena")).toHaveValue(imageId);
  await page.getByLabel("Conteúdo desta cena").selectOption("");
  await expect(page.getByLabel("Enquadramento da imagem")).toHaveCount(0);
  await page
    .getByRole("button", { name: "Salvar alterações", exact: true })
    .click();
  expect(writes.at(-1)).toMatchObject({ scenes: [{ image_id: null }] });
});

test("falha no catálogo tem recuperação sem produzir vídeo", async ({
  page,
}) => {
  await builtApp(page);
  await agents(page);
  await page.route("**/api/projects", (route) => route.fulfill({ json: [] }));
  await page.route(
    "**/api/short-formats",
    (route) => route.fulfill({ status: 503, json: {} }),
    { times: 1 },
  );
  await page.goto("/#/novo");
  await expect(page.getByRole("alert")).toContainText(
    "Não foi possível carregar os formatos",
  );
  await page
    .getByRole("button", { name: "Tentar novamente", exact: true })
    .click();
  await expect(
    page.getByRole("radio", { name: "Editorial", exact: true }),
  ).toBeVisible();
  await page.getByRole("radio", { name: "Editorial", exact: true }).focus();
  await page.keyboard.press("ArrowRight");
  await expect(
    page.getByRole("radio", { name: "Radar tech", exact: true }),
  ).toBeChecked();
});
