import { expect, test } from "@playwright/test";
import type { APIRequestContext, Page } from "@playwright/test";
import { execFileSync, spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const HUMAN = { kind: "human", name: "Autor" };
type Project = {
  id: string;
  revision: number;
  tracks: { id: string; kind: string }[];
  resources: { hash: string; name: string }[];
};
type Export = { id: string; revision: number; state: string; name: string; message: string; duration_ms: number };

const ffmpeg = (...args: string[]) => execFileSync("ffmpeg", ["-v", "error", "-nostdin", "-y", ...args], { encoding: "utf8" });

/** Sample media made on the spot: a still image, a clip with a frame counter and a tone. */
function media(folder: string) {
  ffmpeg("-f", "lavfi", "-i", "testsrc=s=800x600", "-frames:v", "1", join(folder, "imagem.png"));
  ffmpeg("-f", "lavfi", "-i", "testsrc2=s=1280x720:r=30:d=3", "-pix_fmt", "yuv420p", join(folder, "clipe.mp4"));
  ffmpeg("-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100:duration=6", join(folder, "tom.wav"));
}

async function edit(api: APIRequestContext, project: Project, operations: object[]) {
  const response = await api.post(`/api/edit-projects/${project.id}/operations`, {
    data: { revision: project.revision, author: HUMAN, operations },
  });
  expect(response.status(), await response.text()).toBe(200);
  return (await response.json()) as Project;
}

async function finished(api: APIRequestContext, project: Project, id: string) {
  let found: Export | undefined;
  await expect
    .poll(
      async () => {
        const { exports } = await (await api.get(`/api/edit-projects/${project.id}/exports`)).json();
        found = exports.find((e: Export) => e.id === id);
        return found?.state;
      },
      { timeout: 180_000, intervals: [1000] },
    )
    .toMatch(/done|failed/);
  expect(found!.state, found!.message).toBe("done");
  return found!;
}

function probe(file: string) {
  return JSON.parse(
    execFileSync("ffprobe", ["-v", "error", "-show_streams", "-show_format", "-of", "json", file], { encoding: "utf8" }),
  );
}

/** SSIM between a capture of the preview and frame `index` of the MP4, reduced to the capture's size. */
function ssim(shot: string, video: string, index: number) {
  const run = spawnSync("ffmpeg", [
    "-v", "info", "-nostdin", "-i", shot, "-i", video, "-filter_complex",
    `[1:v]select=eq(n\\,${index})[f];[f][0:v]scale2ref=flags=area[b][a];[a]format=yuv420p[x];[b]format=yuv420p[y];[x][y]ssim`,
    "-an", "-frames:v", "1", "-f", "null", "-",
  ], { encoding: "utf8" });
  const found = /All:([0-9.]+)/.exec(run.stderr);
  if (!found) throw new Error(run.stderr);
  return Number(found[1]);
}

async function previewAt(page: Page, ms: number, file: string) {
  const instant = page.getByLabel("Instante (s)");
  await instant.fill(String(ms / 1000));
  await instant.press("Enter");
  const stage = page.getByRole("img", { name: "Quadro da prévia" });
  await expect(stage).toHaveAttribute("data-ms", String(ms));
  await stage.screenshot({ path: file, animations: "disabled" });
}

test("exportar uma revisão congelada em MP4 e conferir a prévia contra o arquivo", async ({ page, request }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "A exportação é a mesma em qualquer tela.");
  test.setTimeout(420_000);
  const folder = mkdtempSync(join(tmpdir(), "mycut-export-"));
  media(folder);

  const created = await request.post("/api/edit-projects", { data: { title: "Exportação de teste", author: HUMAN } });
  let project = (await created.json()) as Project;
  for (const [name, mimeType] of [["imagem.png", "image/png"], ["clipe.mp4", "video/mp4"], ["tom.wav", "audio/wav"]]) {
    const response = await request.post(`/api/edit-projects/${project.id}/resources`, {
      multipart: {
        file: { name, mimeType, buffer: readFileSync(join(folder, name)) },
        revision: String(project.revision), author_kind: "human", author_name: "Autor",
      },
    });
    expect(response.status(), await response.text()).toBe(200);
    project = await response.json();
  }
  const hash = (name: string) => project.resources.find((r) => r.name === name)!.hash;
  const track = (kind: string) => project.tracks.find((t) => t.kind === kind)!.id;
  // Every effect of the list on one short montage: fades, dissolve, zoom and pan, points in time, filters,
  // a typed text, speed and a held frame, a sketch and a tone with fades.
  project = await edit(request, project, [
    { op: "add_item", item: { id: "imagem", track_id: track("visual"), start_ms: 0, duration_ms: 2000, resource: hash("imagem.png"),
                              enter: { kind: "fade", duration_ms: 600 } } },
    { op: "set_keyframes", item_id: "imagem", property: "zoom", points: [{ at_ms: 0, value: 1 }, { at_ms: 2000, value: 1.4, easing: "ease" }] },
    { op: "set_keyframes", item_id: "imagem", property: "pan_x", points: [{ at_ms: 0, value: 0 }, { at_ms: 2000, value: 0.1 }] },
    { op: "set_style", item_id: "imagem", values: { saturation: 1.6, contrast: 1.2 } },
    { op: "add_item", item: { id: "clipe", track_id: track("visual"), start_ms: 2000, duration_ms: 3000, resource: hash("clipe.mp4"),
                              enter: { kind: "dissolve", duration_ms: 600 }, exit: { kind: "fade", duration_ms: 300 } } },
    { op: "update_item", item_id: "clipe", changes: { speed: 2, freeze: { at_ms: 500, duration_ms: 1000 } } },
    { op: "set_style", item_id: "clipe", values: { brightness: 1.2 } },
    { op: "add_item", item: { id: "esboco", track_id: track("visual"), start_ms: 0, duration_ms: 4500, layer: 1,
                              geometry: { x: 1380, y: 60, width: 480, height: 320 } } },
    { op: "set_keyframes", item_id: "esboco", property: "rotation", points: [{ at_ms: 0, value: -8 }, { at_ms: 4500, value: 8 }] },
    { op: "set_style", item_id: "esboco", values: { blur: 2 } },
    { op: "add_item", item: { id: "titulo", track_id: track("text"), start_ms: 0, duration_ms: 4500, text: "Revisão congelada",
                              geometry: { x: 160, y: 820, width: 1600, height: 180 },
                              enter: { kind: "type", duration_ms: 1200 }, exit: { kind: "sink", duration_ms: 500 } } },
    { op: "set_keyframes", item_id: "titulo", property: "scale", points: [{ at_ms: 1200, value: 1 }, { at_ms: 3000, value: 1.15 }] },
    { op: "add_item", item: { id: "tom", track_id: track("music"), start_ms: 0, duration_ms: 4500, resource: hash("tom.wav"),
                              enter: { kind: "fade", duration_ms: 1000 }, exit: { kind: "fade", duration_ms: 500 } } },
    { op: "set_style", item_id: "tom", values: { volume: 0.5 } },
  ]);
  const frozen = project.revision;

  const asked = await request.post(`/api/edit-projects/${project.id}/exports`, { data: { revision: frozen, author: HUMAN } });
  expect(asked.status(), await asked.text()).toBe(201);
  const first = (await asked.json()) as Export;
  expect(first.name).toBe(`exportacao-de-teste-r${frozen}.mp4`);
  // Editing goes on during the export: a longer video with another text, which the file must not show.
  const edited = await edit(request, project, [
    { op: "update_item", item_id: "titulo", changes: { text: "Texto depois da exportação" } },
    { op: "add_item", item: { id: "depois", track_id: track("text"), start_ms: 6000, duration_ms: 2000, text: "Fim" } },
  ]);
  expect(edited.revision).toBe(frozen + 1);
  await finished(request, project, first.id);

  const download = await request.get(`/api/edit-projects/${project.id}/exports/${first.id}/file`);
  expect(download.status()).toBe(200);
  expect(download.headers()["content-disposition"]).toContain(`exportacao-de-teste-r${frozen}.mp4`);
  const video = join(folder, first.name);
  writeFileSync(video, await download.body());
  const info = probe(video);
  const picture = info.streams.find((s: { codec_type: string }) => s.codec_type === "video");
  const sound = info.streams.find((s: { codec_type: string }) => s.codec_type === "audio");
  expect([picture.codec_name, picture.width, picture.height, picture.r_frame_rate, picture.pix_fmt]).toEqual(
    ["h264", 1920, 1080, "30/1", "yuv420p"],
  );
  expect([sound.codec_name, sound.sample_rate, sound.channels]).toEqual(["aac", "48000", 2]);
  expect(Number(picture.nb_frames)).toBe(150);
  // 5 s of the frozen revision, not the 8 s of the edited one.
  expect(Number(info.format.duration)).toBeCloseTo(5, 1);

  // Back to the frozen content (a new revision with the same document) to compare the preview with the file.
  const undo = await request.post(`/api/edit-projects/${project.id}/undo`, { data: { revision: edited.revision, author: HUMAN } });
  expect(undo.status()).toBe(200);
  await page.goto(`/#/edicao/${project.id}`);
  await expect(page.getByRole("heading", { name: "Exportação de teste" })).toBeVisible();
  await expect(page.getByText("preparando os quadros dos vídeos")).toHaveCount(0, { timeout: 60_000 });
  // Reference frames: fade and typing, zoom and pan, dissolve, clip at 2×, held frame, exits and sketch.
  for (const index of [10, 45, 69, 75, 95, 132]) {
    const ms = Math.round((index * 1000) / 30);
    const shot = join(folder, `previa-${index}.png`);
    await previewAt(page, ms, shot);
    const own = ssim(shot, video, index);
    const other = ssim(shot, video, index < 75 ? index + 40 : index - 40);
    testInfo.annotations.push({ type: "SSIM", description: `quadro ${index}: ${own} (outro instante: ${other})` });
    expect.soft(own, `quadro ${index}: SSIM ${own} contra ${other} de outro instante`).toBeGreaterThan(0.85);
    expect.soft(own, `quadro ${index}`).toBeGreaterThan(other);
  }

  // Exports stay until the author removes them.
  const second = (await (await request.post(`/api/edit-projects/${project.id}/exports`, {
    data: { revision: edited.revision + 1, author: HUMAN },
  })).json()) as Export;
  await finished(request, project, second.id);
  let list = (await (await request.get(`/api/edit-projects/${project.id}/exports`)).json()).exports as Export[];
  expect(list.map((e) => e.revision)).toEqual([edited.revision + 1, frozen]);
  const agent = await request.delete(`/api/edit-projects/${project.id}/exports/${first.id}`, {
    data: { author: { kind: "agent", name: "Diretor" } },
  });
  expect(agent.status()).toBe(403);
  await page.getByRole("button", { name: `Remover ${first.name}` }).last().click();
  await page.getByRole("button", { name: "Confirmar remoção", exact: true }).click();
  await expect(page.getByRole("list", { name: "Exportações do projeto" }).getByRole("listitem")).toHaveCount(1);
  list = (await (await request.get(`/api/edit-projects/${project.id}/exports`)).json()).exports as Export[];
  expect(list.map((e) => e.id)).toEqual([second.id]);
  expect((await request.get(`/api/edit-projects/${project.id}/exports/${first.id}/file`)).status()).toBe(404);
});
