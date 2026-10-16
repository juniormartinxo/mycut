import { expect, test } from "@playwright/test";
import { existsSync, mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { resolve } from "node:path";
import { execFileSync, spawn } from "node:child_process";

// Short livre ponta a ponta (MYC-8): the reference prompt on the real server and worker. Only the agents' CLIs are
// simulated, by the local runner fixture that answers from backend/tests/reference_agents.py.
const testPython =
  process.env.MYCUT_TEST_PYTHON ||
  ["../.venv-app/bin/python", "../.venv-narration/bin/python"].map((p) => resolve(p)).find((p) => existsSync(p)) ||
  "python3";
const prompt = readFileSync(resolve("../backend/tests/fixtures/prompt-de-referencia.md"), "utf8");
const narration = [
  "Seus vídeos de IA mudam de rosto a cada cena? O problema não é a ferramenta.",
  "É que você pula a pré-produção. Olha: tudo começa com uma frase simples.",
  "Primeiro, o tom: gênero, paleta e luz. Isso vira a regra de todas as cenas.",
  "Depois, a ficha do personagem com números exatos: idade, altura, peso, cicatriz. Número a IA não inventa.",
  "Terceiro, o cenário sozinho, sem ninguém. Ele vira a referência fixa do mundo.",
  "Por último, a decupagem: plano, movimento de câmera e física. Você anexa ficha e cenário em cada cena e o rosto não muda mais.",
  "Resultado: isso. O prompt completo está no comentário fixado.",
];

test("o prompt de referência vira um Short livre: criação, bases, materiais, fala editada e proposta do agente", async ({
  page,
}, info) => {
  test.skip(!process.env.MYCUT_BLOCK_TEST_DATA, "Requer a instância isolada com worker e fixture de agente em /tmp.");
  const runner = spawn(testPython, [resolve("tests/fixtures/scene_agent_runner.py")], { env: process.env });
  const directory = mkdtempSync(resolve(tmpdir(), "mycut-reference-"));
  const shot = (name: string) => page.screenshot({ path: info.outputPath(`${name}.png`), fullPage: true });
  const fits = () =>
    expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  try {
    const picture = resolve(directory, "ira-referencia.png");
    const clip = resolve(directory, "ira-avanca.mp4");
    execFileSync(testPython, ["-c", "from PIL import Image; import sys; Image.new('RGB',(96,64),'#335566').save(sys.argv[1])", picture]);
    execFileSync("ffmpeg", ["-v", "error", "-f", "lavfi", "-i", "color=c=red:s=180x320:d=2:r=30", "-pix_fmt", "yuv420p", clip]);
    await expect.poll(async () => (await (await page.request.get("/api/integrations")).json()).runner.online).toBe(true);

    // New › Livre: the whole prompt, a reference image, script and scenes first, the bases reviewed first.
    await page.goto("/#/novo");
    await page.getByRole("radio", { name: "Livre", exact: true }).check();
    await page.getByLabel("Prompt do Short livre").fill(prompt);
    await page.locator(".free-attachments input[type=file]").setInputFiles(picture);
    await page.getByLabel("Roteiro e cenas primeiro").check();
    await expect(
      page.getByRole("group", { name: "Imagens da Arte" }).getByRole("radio", { name: /Conferir as imagens-base primeiro/ }),
    ).toBeChecked();
    await fits();
    await page.getByRole("button", { name: "Criar roteiro com agentes" }).click();
    await expect(page).toHaveURL(/#\/producoes\/[a-f0-9]{32}/);
    const id = page.url().match(/producoes\/([a-f0-9]{32})/)![1];
    const project = async () => (await page.request.get(`/api/projects/${id}`)).json();

    // The production stops with the bases ready, before the voice.
    await expect
      .poll(async () => ((await project()).art?.requests ?? []).filter((r: { state: string }) => r.state === "generated").length, {
        timeout: 60_000,
      })
      .toBe(2);
    await expect.poll(async () => (await project()).jobs.every((job: { state: string }) => job.state !== "running" && job.state !== "queued")).toBe(true);
    await page.goto(`/#/producoes/${id}/art`);
    const bases = page.getByRole("region", { name: "Imagens-base" });
    await expect(bases.getByRole("img", { name: "Ficha da Comandante Ira Vale" })).toBeVisible();
    await expect(bases.getByRole("img", { name: "Corredor vazio da Halcyon" })).toBeVisible();
    await expect(page.getByRole("region", { name: "Bíblia visual" })).toContainText("Comandante Ira Vale");
    await fits();
    await shot("referencia-bases");
    await page.getByRole("button", { name: "Gerar as 4 imagens que faltam" }).click();
    await expect
      .poll(async () => ((await project()).art.requests as { state: string }[]).every((r) => r.state === "generated"), {
        timeout: 60_000,
      })
      .toBe(true);

    // The script follows the prompt; the author edits the speech before any voice is generated.
    await page.goto(`/#/producoes/${id}/script`);
    for (const [index, text] of narration.entries())
      await expect(page.getByLabel(`Narração da cena ${index + 1}`)).toHaveValue(text);
    await expect(page.getByText("Pausa de 0,8 s depois de “Resultado: isso.”")).toBeVisible();
    await page.getByLabel("Narração da cena 2").fill(narration[1].replace("uma frase simples", "uma frase bem simples"));
    await page.getByRole("button", { name: "Salvar" }).first().click();
    await expect.poll(async () => (await project()).scenes[1].narration).toContain("uma frase bem simples");
    expect((await project()).audio).toBeFalsy();

    // The publication package the prompt asks for.
    await page.getByRole("tab", { name: "Publicação" }).click();
    await expect(page.getByRole("list", { name: "Opções de título" }).getByRole("listitem")).toHaveCount(3);
    await expect(page.getByText("#Shorts #IA #InteligenciaArtificial", { exact: false })).toBeVisible();

    // The lista de materiais: six B-rolls waiting; the clip made outside fills the plano of Ira in the corridor.
    await page.getByRole("tab", { name: "Materiais" }).click();
    const list = page.getByRole("list", { name: "Lista de materiais" });
    await expect(list.getByRole("listitem")).toHaveCount(6);
    const moving = list.getByRole("listitem").filter({ hasText: "Ira avança pelo corredor" });
    await expect(moving).toContainText("Kling/Runway · 5 s");
    await expect(moving).toContainText("Entra em: cena 6, plano 4");
    await expect(moving).toContainText("Aguardando clipe");
    await fits();
    await shot("referencia-materiais");
    await moving.getByLabel("Importar clipe do B-roll 4").setInputFiles(clip);
    await expect(moving).toContainText("Clipe importado");
    const imported = await project();
    expect(imported.scenes[5].shots[2].background).toMatchObject({ kind: "video", broll: "ira-avanca" });
    expect(imported.scenes[5].shots[2].background.asset_id).toBe(imported.videos.at(-1).id);

    // Later editing: the scene opens in the editor and the agent's proposal changes only after it is accepted.
    await page.getByRole("tab", { name: "Cenas" }).click();
    await page.getByRole("button", { name: "Editar cena 4", exact: true }).click();
    await page.getByRole("button", { name: "Editar cena", exact: true }).click();
    const dialog = page.getByRole("dialog");
    await dialog.getByRole("navigation", { name: "Planos da cena" }).getByRole("button", { name: /^Plano 2/ }).click();
    await dialog.getByRole("button", { name: "Selecionar bloco 2", exact: true }).click();
    await dialog.getByRole("tab", { name: "Agente", exact: true }).click();
    await dialog.getByRole("textbox", { name: "Mensagem para o agente", exact: true }).fill("Deixe a ficha mais clara.");
    await dialog.getByRole("button", { name: "Enviar ao agente", exact: true }).click();
    await dialog.getByRole("button", { name: "Revisar proposta", exact: true }).click({ timeout: 60_000 });
    expect((await project()).scenes[3].shots[0].blocks[1].object.text).toContain("Idade: 38 anos");
    await dialog.getByRole("button", { name: "Aceitar proposta", exact: true }).click();
    await expect(dialog.getByText("Proposta aceita", { exact: true })).toBeVisible();
    await expect.poll(async () => (await project()).scenes[3].shots[0].blocks[1].object.text).toBe("Uma ideia mais clara");
    await shot("referencia-proposta");
  } finally {
    runner.kill("SIGTERM");
    await new Promise<void>((done) => {
      runner.once("exit", () => done());
      setTimeout(done, 3000);
    });
    rmSync(directory, { recursive: true, force: true });
  }
});
