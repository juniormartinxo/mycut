import { test, expect, type Page } from "@playwright/test";
import { builtApp } from "./fixtures/builtApp";
import type { Background, Broll, Project } from "../src/types";

const id = "abcdef0123456789abcdef0123456789";
const still = "1".repeat(32);
const corridor = "2".repeat(32);
const clip = "3".repeat(32);
// Local, synthetic PNG; never an external image or provider request.
const png = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADUlEQVQIHWP4z8AAAAMBAQDJ/pLvAAAAAElFTkSuQmCC",
  "base64",
);
const image = (key: string, name: string) => ({
  id: key, name, url: `/api/projects/${id}/images/${key}`, width: 1080, height: 1920, source_url: "", page_url: "",
});
const video = { id: clip, name: "corredor.mp4", url: `/api/projects/${id}/scene-videos/${clip}/video`,
  poster_url: `/api/projects/${id}/scene-videos/${clip}/poster`, width: 1080, height: 1920, duration: 5 };
const waiting = (asset_id: string, broll: string): Background =>
  ({ kind: "image", asset_id, motion: "zoom_in", dim: 20, broll });
const filled = (broll: string): Background => ({ kind: "video", asset_id: clip, motion: "none", dim: 20, broll });

function broll(key: string, title: string, tool: string, seconds: number, prompt: string, references: string[],
  scene: number): Broll {
  return { key, title, tool, seconds, prompt, references, places: [{ scene, shot: 1, waiting: true }] };
}

/** A Short livre whose two B-rolls still wait for their clips, each on the Arte's image with camera motion. */
function project(): Project {
  const scene = (number: number, background: Background) => ({
    id: `${number}`.repeat(32).replace(/^./, "a"),
    title: `Cena ${number}`, narration: "Seus vídeos de IA mudam de rosto a cada cena?", layout: "statement" as const,
    items: [], background, brand: false,
    blocks: [{ id: `${number}`.repeat(32).replace(/^./, "b"), width: 100, height: 100, align: "center" as const, object: null }],
  });
  return {
    id, title: "Da ideia ao filme com IA", brief: "# Short: Da Ideia ao Filme com IA", free: true, warnings: [],
    description: "", tags: "", sources: "", accent: "#F2B544", accent_locked: false, visual_style: null,
    images: [image(still, "Três rostos da astronauta"), image(corridor, "Corredor vazio da Halcyon")], videos: [],
    art: { mode: "all", bible: null, estimate: null, then: null, requests: [
      { key: "corredor", base: true, title: "Corredor vazio da Halcyon", prompt: "Empty corridor", references: [],
        aspect: "9:16", state: "generated", image_id: corridor, error: "", messages: [], outdated: false }] },
    brolls: [
      broll("rostos", "Gancho: o mesmo personagem com 3 rostos", "Midjourney/Flux, 3 gerações", 3,
        "Close-up portrait, 50mm lens, a female astronaut in a white spacesuit --ar 9:16", [], 1),
      broll("corredor-vivo", "Corredor vivo", "Kling/Runway", 5,
        "Wide shot, 24mm lens, slow dolly forward down an abandoned spaceship corridor, no people", ["corredor"], 2),
    ],
    scenes: [scene(1, waiting(still, "rostos")), scene(2, waiting(corridor, "corredor-vivo"))],
    revision: 2, created_at: 0, updated_at: 0, jobs: [], audio_matches_script: false,
    usage_total: { input: 0, cache_read: 0, cache_write: 0, output: 0, reasoning: 0, web_searches: 0, credits: 0, usd: 0, unpriced: 0 },
  } as Project;
}

/** What the API answers after the clip of a B-roll is imported: it fills the plano and the place stops waiting. */
function imported(current: Project, key: string): Project {
  return {
    ...current, revision: current.revision + 1, videos: [video],
    scenes: current.scenes.map((scene) => scene.background?.broll === key ? { ...scene, background: filled(key) } : scene),
    brolls: current.brolls!.map((item) => item.key === key
      ? { ...item, clip: { kind: "video", id: clip }, places: item.places.map((place) => ({ ...place, waiting: false })) } : item),
  };
}

async function api(page: Page, state: { project: Project; posted: string[] }) {
  await builtApp(page);
  await page.route("**/api/integrations", (route) => route.fulfill({ json: {
    agents: Object.fromEntries(["research", "writer", "director", "reviewer", "art"].map((role) => [role, { provider: "codex", model: "" }])),
    runner: { online: true, providers: { codex: true, claude: true, grok: true } },
    elevenlabs: { connected: false }, pricing: { models: {}, images: { codex: 0.05, grok: null } },
  } }));
  await page.route("**/api/projects", (route) => route.fulfill({ json: [state.project] }));
  await page.route(`**/api/projects/${id}`, (route) => {
    if (route.request().method() === "PUT") {
      state.project = { ...state.project, ...route.request().postDataJSON(), revision: state.project.revision + 1 };
    }
    return route.fulfill({ json: state.project });
  });
  await page.route(`**/api/projects/${id}/images/*`, (route) => route.fulfill({ body: png, contentType: "image/png" }));
  await page.route(`**/api/projects/${id}/scene-videos/**`, (route) => route.fulfill({ body: png, contentType: "image/png" }));
  await page.route(`**/api/projects/${id}/scene-conversations`, (route) => route.fulfill({ json: { threads: [], messages: [] } }));
  await page.route("**/api/scene-layout/inspect", (route) => route.fulfill({ json: { issues: [], warnings: [], geometry: [] } }));
  await page.route(`**/api/projects/${id}/brolls/*/clip?**`, (route) => {
    const url = route.request().url();
    state.posted.push(url);
    state.project = imported(state.project, url.split("/brolls/")[1].split("/")[0]);
    return route.fulfill({ json: state.project });
  });
}

test("a lista de materiais diz o que falta e o clipe importado ocupa o plano do B-roll", async ({ page }, info) => {
  const state = { project: project(), posted: [] as string[] };
  await api(page, state);

  // The production says what is missing: which clips, in which plano, with which tool.
  await page.goto(`/#/producoes/${id}/brief`);
  const missing = page.getByRole("region", { name: "Clipes de B-roll que faltam" });
  await expect(missing).toContainText("Faltam 2 clipes de B-roll");
  await expect(missing).toContainText("B-roll 2 · Corredor vivo · cena 2, plano 1 · Kling/Runway · 5 s");
  await expect(missing).toContainText("a exportação continua liberada");
  await expect(missing.getByText("slow dolly forward down an abandoned spaceship corridor")).toBeAttached();
  await missing.getByRole("button", { name: "Abrir a lista de materiais" }).click();
  await expect(page.getByRole("tab", { name: "Materiais" })).toHaveAttribute("aria-selected", "true");

  // The list: each B-roll with its prompt, tool, references and duration.
  const list = page.getByRole("list", { name: "Lista de materiais" });
  const corridorCard = list.getByRole("listitem").filter({ hasText: "Corredor vivo" });
  await expect(list.getByRole("listitem")).toHaveCount(2);
  await expect(corridorCard).toContainText("Aguardando clipe");
  await expect(corridorCard).toContainText("Kling/Runway · 5 s");
  await expect(corridorCard).toContainText("Entra em: cena 2, plano 1");
  // A B-roll made in Midjourney or Flux is an image: the import takes images too.
  await expect(corridorCard.getByLabel("Importar clipe do B-roll 2")).toHaveAttribute("accept", /image\/png/);
  await expect(corridorCard).toContainText("slow dolly forward down an abandoned spaceship corridor");
  await expect(corridorCard.getByRole("img", { name: "Corredor vazio da Halcyon" })).toBeVisible();
  await expect(list.getByRole("listitem").filter({ hasText: "Gancho" })).toContainText("Referências: nenhuma");
  await page.screenshot({ path: info.outputPath("materiais.png"), fullPage: true });

  await corridorCard.getByLabel("Importar clipe do B-roll 2").setInputFiles(
    { name: "corredor.mp4", mimeType: "video/mp4", buffer: Buffer.from("clipe") });
  await expect(corridorCard).toContainText("Clipe importado");
  expect(state.posted[0]).toContain(`/api/projects/${id}/brolls/corredor-vivo/clip?revision=2`);
  await expect(page.getByRole("region", { name: "Clipes de B-roll que faltam" })).toContainText("Falta 1 clipe de B-roll");

  // In the editor: the plano waiting for its clip has a seal, and the clip can be imported from there.
  await page.getByRole("tab", { name: "Cenas" }).click();
  await expect(page.getByRole("region", { name: "Clipes de B-roll que faltam" })).toContainText("B-roll 1 · Gancho");
  await page.getByRole("button", { name: "Editar cena", exact: true }).click();
  const dialog = page.getByRole("dialog");
  const strip = dialog.getByRole("navigation", { name: "Planos da cena" });
  await expect(strip.getByRole("button", { name: /^Plano 1/ })).toHaveAccessibleName(/aguardando clipe/);
  await expect(dialog.getByText("Aguardando clipe", { exact: true }).first()).toBeVisible();
  await dialog.getByRole("tab", { name: "Plano", exact: true }).click();
  const waitingClip = dialog.getByRole("group", { name: "B-roll deste plano" });
  await expect(waitingClip).toContainText("B-roll 1 · Gancho: o mesmo personagem com 3 rostos");
  await expect(waitingClip).toContainText("Midjourney/Flux, 3 gerações · 3 s");
  await dialog.screenshot({ path: info.outputPath("editor-aguardando-clipe.png") });
  await waitingClip.getByLabel("Importar clipe do B-roll 1").setInputFiles(
    { name: "rostos.mp4", mimeType: "video/mp4", buffer: Buffer.from("clipe") });
  await expect(waitingClip).toContainText("Clipe importado");
  await expect(strip.getByRole("button", { name: /^Plano 1/ })).not.toHaveAccessibleName(/aguardando clipe/);
  expect(state.posted[1]).toContain("/brolls/rostos/clip");
  // The import changed other planos on the server too: there is nothing to undo here.
  await expect(dialog.getByRole("button", { name: "Desfazer", exact: true })).toBeDisabled();
  await dialog.getByRole("button", { name: "Fechar", exact: true }).click();
  await expect(page.getByRole("region", { name: "Clipes de B-roll que faltam" })).toHaveCount(0);
});
