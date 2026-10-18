import assert from "node:assert/strict";
import { test } from "node:test";
import { audioPlan, frameAt, frameCount, frameTime } from "../src/engine/timeline.ts";
import type { Montage, MontageItem } from "../src/engine/timeline.ts";

const FORMAT = { width: 1920, height: 1080, fps: 30 };
const TRACKS = [
  { id: "visuais", kind: "visual" as const, name: "Visuais" },
  { id: "textos", kind: "text" as const, name: "Textos" },
  { id: "musica", kind: "music" as const, name: "Música" },
];
const RESOURCES = [
  { hash: "c".repeat(64), name: "clipe.mp4", media_type: "video/mp4", size: 1 },
  { hash: "a".repeat(64), name: "trilha.wav", media_type: "audio/wav", size: 1 },
];

function item(values: Partial<MontageItem> & Pick<MontageItem, "id" | "track_id" | "start_ms" | "duration_ms">): MontageItem {
  const visual = values.track_id !== "musica";
  return {
    scene_id: null,
    source_start_ms: 0,
    layer: 0,
    geometry: visual ? { x: 0, y: 0, width: 1920, height: 1080 } : null,
    text: null,
    resource: null,
    resolved_style: {},
    keyframes: {},
    enter: null,
    exit: null,
    speed: 1,
    freeze: null,
    ...values,
  };
}

function montage(items: MontageItem[]): Montage {
  const end = Math.max(1000, ...items.map((i) => i.start_ms + i.duration_ms));
  return { format: FORMAT, tracks: TRACKS, resources: RESOURCES, items, duration_ms: end };
}

const layer = (m: Montage, ms: number, id: string) => frameAt(m, ms).layers.find((l) => l.id === id);

test("um quadro e uma amostra saem do índice, sem deriva numa montagem de 25 minutos", () => {
  // 1.500 itens de 1.001 ms em sequência: nenhum começa num quadro inteiro a 30 qps.
  const items = Array.from({ length: 1500 }, (_, k) =>
    item({ id: `i${k}`, track_id: "visuais", start_ms: k * 1001, duration_ms: 1001 }),
  );
  const music = item({ id: "trilha", track_id: "musica", start_ms: 0, duration_ms: 1_501_500, resource: RESOURCES[1].hash });
  const m = montage([...items, music]);
  assert.equal(frameCount(m), 45_045);
  assert.equal(frameTime(45_000, 30), 1_500_000);
  // 1.500.000 ms caem no item 1498 (de 1.499.498 a 1.500.499 ms).
  assert.deepEqual(frameAt(m, frameTime(45_000, 30)).layers.map((l) => l.id), ["i1498"]);
  assert.deepEqual(frameAt(m, frameTime(44_985, 30)).layers.map((l) => l.id), ["i1498"]);
  assert.deepEqual(frameAt(m, frameTime(44_984, 30)).layers.map((l) => l.id), ["i1497"]);
  // O último quadro ainda mostra o último item.
  assert.deepEqual(frameAt(m, frameTime(45_044, 30)).layers.map((l) => l.id), ["i1499"]);
  const plan = audioPlan(m, 48_000);
  assert.equal(plan[0].startSample, 0);
  assert.equal(plan[0].endSample, 72_072_000);
});

test("velocidade e congelamento escolhem o momento da mídia a partir do início do clipe", () => {
  const clip = item({
    id: "clipe", track_id: "visuais", start_ms: 1_200_000, duration_ms: 20_000, source_start_ms: 3000,
    resource: RESOURCES[0].hash, speed: 1.5, freeze: { at_ms: 4000, duration_ms: 2000 },
  });
  const m = montage([clip]);
  const at = (ms: number) => layer(m, ms, "clipe")!.media!.sourceMs;
  assert.equal(at(1_200_000), 3000);
  assert.equal(at(1_202_000), 6000);
  // De 4 s a 6 s do clipe, o quadro de 9 s da mídia fica parado.
  assert.equal(at(1_204_000), 9000);
  assert.equal(at(1_205_500), 9000);
  assert.equal(at(1_210_000), 15_000);
  assert.equal(layer(m, 1_220_000, "clipe"), undefined);
});

test("os itens depois de um clipe acelerado continuam no próprio quadro", () => {
  const fast = item({ id: "rapido", track_id: "visuais", start_ms: 0, duration_ms: 3333, speed: 1.5 });
  const next = item({ id: "depois", track_id: "visuais", start_ms: 3333, duration_ms: 2000 });
  const m = montage([fast, next]);
  // 3.333 ms ficam entre os quadros 99 (3.300 ms) e 100 (3.333,3 ms).
  assert.deepEqual(frameAt(m, frameTime(99, 30)).layers.map((l) => l.id), ["rapido"]);
  assert.deepEqual(frameAt(m, frameTime(100, 30)).layers.map((l) => l.id), ["depois"]);
});

test("pontos no tempo interpolam cada propriedade com a curva do ponto anterior", () => {
  const points = (easing: "linear" | "ease" | "hold") => [
    { at_ms: 0, value: 0, easing },
    { at_ms: 1000, value: 1, easing },
  ];
  const m = montage([
    item({ id: "linear", track_id: "visuais", start_ms: 0, duration_ms: 2000, keyframes: { opacity: points("linear") } }),
    item({ id: "suave", track_id: "visuais", start_ms: 0, duration_ms: 2000, keyframes: { opacity: points("ease") } }),
    item({ id: "degrau", track_id: "visuais", start_ms: 0, duration_ms: 2000, keyframes: { opacity: points("hold") } }),
    item({
      id: "girando", track_id: "visuais", start_ms: 0, duration_ms: 2000,
      resolved_style: { scale: { value: 2, inherited: false } },
      keyframes: { rotation: [{ at_ms: 500, value: 90, easing: "linear" }, { at_ms: 1500, value: 180, easing: "linear" }],
                   x: [{ at_ms: 0, value: 100, easing: "linear" }, { at_ms: 2000, value: 300, easing: "linear" }] },
    }),
  ]);
  assert.equal(layer(m, 250, "linear")!.opacity, 0.25);
  assert.equal(layer(m, 500, "suave")!.opacity, 0.5);
  assert.ok(layer(m, 250, "suave")!.opacity < 0.25);
  assert.equal(layer(m, 999, "degrau")!.opacity, 0);
  assert.equal(layer(m, 1500, "degrau")!.opacity, 1);
  const turning = layer(m, 1000, "girando")!;
  // Antes do primeiro ponto vale o primeiro valor; uma propriedade sem pontos fica no valor do estilo.
  assert.deepEqual([layer(m, 0, "girando")!.rotation, turning.rotation, turning.box.x, turning.scale], [90, 135, 200, 2]);
});

test("corte, fusão e fades decidem quem aparece e com que opacidade", () => {
  const m = montage([
    item({ id: "antes", track_id: "visuais", start_ms: 0, duration_ms: 2000, enter: { kind: "fade", duration_ms: 1000 } }),
    item({ id: "fusao", track_id: "visuais", start_ms: 2000, duration_ms: 2000, enter: { kind: "dissolve", duration_ms: 600 } }),
    item({ id: "corte", track_id: "visuais", start_ms: 4000, duration_ms: 1000, exit: { kind: "fade", duration_ms: 500 } }),
  ]);
  assert.equal(layer(m, 250, "antes")!.opacity, 0.25);
  assert.equal(layer(m, 4750, "corte")!.opacity, 0.5);
  // Na fusão, o item anterior fica inteiro por baixo até ser coberto.
  const crossing = frameAt(m, 2300).layers;
  assert.deepEqual(crossing.map((l) => [l.id, l.opacity]), [["antes", 1], ["fusao", 0.5]]);
  assert.deepEqual(frameAt(m, 2600).layers.map((l) => l.id), ["fusao"]);
  assert.deepEqual(frameAt(m, 4000).layers.map((l) => [l.id, l.opacity]), [["corte", 1]]);
});

test("o item coberto por uma fusão segue tocando por baixo, sem a própria saída", () => {
  const m = montage([
    item({ id: "antes", track_id: "visuais", start_ms: 0, duration_ms: 2000, resource: RESOURCES[0].hash,
           exit: { kind: "fade", duration_ms: 500 } }),
    item({ id: "fusao", track_id: "visuais", start_ms: 2000, duration_ms: 2000, enter: { kind: "dissolve", duration_ms: 600 } }),
  ]);
  // The dissolve takes the place of the exit: no fade to black before it, no flash when it starts.
  assert.equal(layer(m, 1750, "antes")!.opacity, 1);
  assert.deepEqual([layer(m, 2300, "antes")!.opacity, layer(m, 2300, "antes")!.media!.sourceMs], [1, 2300]);
});

test("textos entram e saem: digitação revela letras, subida desloca, saída esmaece", () => {
  const m = montage([
    item({
      id: "titulo", track_id: "textos", start_ms: 0, duration_ms: 3000, text: "Olá, mundo",
      enter: { kind: "type", duration_ms: 1000 }, exit: { kind: "sink", duration_ms: 1000 },
    }),
    item({ id: "sobe", track_id: "textos", start_ms: 0, duration_ms: 3000, text: "Sobe", enter: { kind: "rise", duration_ms: 1000 } }),
  ]);
  assert.equal(layer(m, 500, "titulo")!.text!.visibleChars, 5);
  assert.equal(layer(m, 1000, "titulo")!.text!.visibleChars, 10);
  assert.equal(layer(m, 2500, "titulo")!.opacity, 0.5);
  assert.ok(layer(m, 2500, "titulo")!.text!.offsetY > 0);
  assert.ok(layer(m, 0, "sobe")!.text!.offsetY > layer(m, 500, "sobe")!.text!.offsetY);
  assert.equal(layer(m, 1000, "sobe")!.text!.offsetY, 0);
});

test("o plano de áudio põe cada item na amostra exata, com volume e fades", () => {
  const m = montage([
    item({
      id: "trilha", track_id: "musica", start_ms: 1001, duration_ms: 3000, source_start_ms: 500, resource: RESOURCES[1].hash,
      resolved_style: { volume: { value: 0.5, inherited: false } },
      enter: { kind: "fade", duration_ms: 1000 }, exit: { kind: "fade", duration_ms: 500 },
    }),
    item({ id: "sem-midia", track_id: "musica", start_ms: 0, duration_ms: 1000 }),
  ]);
  assert.deepEqual(audioPlan(m, 48_000), [{
    id: "trilha", resource: RESOURCES[1].hash, startSample: 48_048, endSample: 192_048, offsetSeconds: 0.5,
    volume: 0.5, fadeInSamples: 48_000, fadeOutSamples: 24_000,
  }]);
});
